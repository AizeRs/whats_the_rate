from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, request, url_for, jsonify, get_template_attribute
from flask_login import current_user
from app.models import db_session
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import (
    update_tickers_db, update_crypto_db, update_currencies_db,
    get_stocks_by_letter, get_stocks_by_tickers, get_crypto_by_letter, get_crypto_updated_at, get_all_fiats,
    save_ticker_price
)
from app.services.api_client import fetch_quote
from app.formatting import fmt_number_ru, fmt_money_ru, ticker_hue, user_currency, MONTHS_GENITIVE, to_user_tz
from app.presenters import (
    stock_row, fiat_rows, MAX_STOCKS_IN_PORTFOLIO, CRYPTO_AUTO_REFRESH_AFTER, FIAT_AUTO_REFRESH_AFTER
)

market_bp = Blueprint('market', __name__)

def handle_add_asset(request_form_key, asset_type, param):
    """Helper function to process adding an asset to the user's portfolio."""
    raw_val = request.form.get(request_form_key)
    qty = 1.0
    if not raw_val and request.is_json:
        raw_val = request.json.get(request_form_key)
        try:
            qty = float(request.json.get('quantity', 1))
        except (ValueError, TypeError):
            qty = 1.0
    elif request.form.get('quantity'):
        try:
            qty = float(request.form.get('quantity', 1))
        except (ValueError, TypeError):
            qty = 1.0

    if qty <= 0:
        qty = 1.0
    if qty.is_integer():
        qty = int(qty)

    if raw_val and current_user.is_authenticated:
        parts = str(raw_val).split()
        ticker = parts[1] if len(parts) > 1 else parts[0]
        with db_session.create_session() as db_sess:
            pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
            if not pf:
                param['danger'] = f'{ticker}_a'
            else:
                existing_qty = pf.get_dict().get(asset_type, {}).get(ticker, 0)
                try:
                    total_qty = float(existing_qty) + qty
                except (ValueError, TypeError):
                    total_qty = qty
                if total_qty.is_integer():
                    total_qty = int(total_qty)
                if pf.set_in_dict(asset_type, ticker, total_qty) != 'Too Many Stocks Error':
                    db_sess.commit()
                    param['success'] = f'{ticker}_a'
                else:
                    param['danger'] = f'{ticker}_a'
# --- Stocks -----------------------------------------------------------------

STOCKS_PER_PAGE = 50


def _render_stock_cells(row):
    """HTML of the price (and portfolio value) cells, shared by the template and AJAX responses."""
    macros = get_template_attribute('_stock_macros.html', 'price_cell')
    value = get_template_attribute('_stock_macros.html', 'value_cell')
    return str(macros(row)), str(value(row))


def _stocks_ajax_response():
    """Handles POST actions of the stocks pages. Returns a response, or None if nothing matched."""
    data = request.get_json(silent=True) or request.form
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    # Reload the list of tickers (prices are not affected)
    if data.get('reload_tickers'):
        success = update_tickers_db()
        if is_ajax:
            return jsonify({'success': bool(success)})
        return redirect(request.path + ('?reload=1' if success else '?reload=2'))

    # Refresh the price of one stock
    ticker = data.get('reload_rate')
    if ticker:
        ticker = str(ticker).split()[-1]
        status, quote = fetch_quote(ticker)
        if status == 'ok':
            save_ticker_price(ticker, quote['c'], quote.get('dp'))
        stock = next(iter(get_stocks_by_tickers([ticker])), None)
        if not stock:
            return jsonify({'success': False, 'status': 'error'})
        row = stock_row(stock, _portfolio_assets('stocks'))
        price_html, value_html = _render_stock_cells(row)
        return jsonify({'success': status == 'ok', 'status': status, 'price_num': row['price_num'],
                        'price_html': price_html, 'value_html': value_html})

    # Add to the portfolio or set an exact quantity
    if data.get('add_stock') or data.get('set_stock'):
        return _portfolio_quantity_response('stocks', data.get('add_stock'), data.get('set_stock'), data)
    return None


def _portfolio_quantity_response(kind, add_ticker, set_ticker, data):
    """AJAX: adds a quantity to an asset in the portfolio (add_ticker) or sets it exactly (set_ticker)."""
    ticker = str(add_ticker or set_ticker)
    try:
        qty = float(str(data.get('quantity', '')).replace(' ', '').replace(',', '.'))
    except (ValueError, TypeError):
        qty = None
    if add_ticker and (qty is None or qty <= 0):
        qty = 1.0
    result = 'error'
    if current_user.is_authenticated and current_user.portfolio_id is not None and qty is not None and qty >= 0:
        if add_ticker:
            qty += float(_portfolio_assets(kind).get(ticker, 0) or 0)
        result = _set_asset_quantity(kind, ticker, qty)
    holdings = _portfolio_assets(kind)
    quantity = holdings.get(ticker, 0)
    return jsonify({'success': result == 'ok', 'reason': result, 'ticker': ticker,
                    'quantity': quantity, 'quantity_str': fmt_number_ru(quantity),
                    'stocks_count': len(holdings)})


def _stocks_common_params():
    code, sign, _ = user_currency()
    holdings = _portfolio_assets('stocks')
    reload_arg = request.args.get('reload')
    return holdings, {
        'currency_code': code,
        'currency_sign': sign,
        'has_portfolio': current_user.is_authenticated and current_user.portfolio_id is not None,
        'stocks_full': len(holdings) >= MAX_STOCKS_IN_PORTFOLIO,
        'reload': int(reload_arg) if reload_arg in ('1', '2') else None,
    }


@market_bp.route('/stocks', methods=['GET', 'POST'])
def stocks():
    """Start page: search, first-letter filter and the user's own stocks."""
    if request.method == 'POST':
        response = _stocks_ajax_response()
        if response is not None:
            return response

    holdings, param = _stocks_common_params()
    param.update({'is_start': True, 'letter': '', 'is_search': False, 'search_query': '',
                  'stocks': [stock_row(s, holdings) for s in get_stocks_by_tickers(holdings.keys())]})
    return render_template('available_stocks.html', **param)


@market_bp.route('/stocks/<string:letter>', methods=['GET', 'POST'])
def available_stocks_for_letter(letter):
    """Stocks whose ticker starts with a letter, or search results by ticker / company name."""
    if request.method == 'POST':
        response = _stocks_ajax_response()
        if response is not None:
            return response

    query = letter.strip()
    is_search = len(query) > 1
    page = max(request.args.get('page', 1, type=int), 1)

    holdings, param = _stocks_common_params()
    raw_stocks, has_next = get_stocks_by_letter(query, page, STOCKS_PER_PAGE)
    param.update({
        'is_start': False,
        'letter': '' if is_search else query.upper(),
        'is_search': is_search,
        'search_query': query if is_search else '',
        'page': page,
        'has_next': has_next,
        'stocks': [stock_row(s, holdings) for s in raw_stocks],
    })
    return render_template('available_stocks_for_letter.html', **param)


# --- Helpers for the crypto page -------------------------------------------

# Don't retry the automatic reload more often than this (CoinGecko's keyless API allows ~10-30 calls/min)
_CRYPTO_AUTO_RETRY_AFTER = timedelta(minutes=1)
_crypto_last_auto_attempt = None


def _crypto_updated_label(updated_at):
    if not updated_at:
        return None
    shown, shown_now = to_user_tz(updated_at), to_user_tz(datetime.now())
    if shown.date() == shown_now.date():
        return f'в {shown:%H:%M}'
    return f'{shown:%d.%m} в {shown:%H:%M}'


def _portfolio_assets(kind):
    """Returns one part of the current user's portfolio ('stocks', 'crypto', 'fiat') as {SYMBOL: quantity}."""
    if not (current_user.is_authenticated and current_user.portfolio_id is not None):
        return {}
    with db_session.create_session() as db_sess:
        pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
        if not pf:
            return {}
        return dict(pf.get_dict().get(kind, {}))


def _set_asset_quantity(kind, ticker, qty):
    """Sets an exact quantity of an asset in the user's portfolio (0 removes it).

    Returns 'ok', 'limit' (too many stocks) or 'error'.
    """
    if float(qty).is_integer():
        qty = int(qty)
    with db_session.create_session() as db_sess:
        pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
        if not pf:
            return 'error'
        if pf.set_in_dict(kind, ticker, qty) == 'Too Many Stocks Error':
            return 'limit'
        db_sess.commit()
        return 'ok'


def _crypto_holdings():
    return _portfolio_assets('crypto')


def _set_crypto_quantity(ticker, qty):
    return _set_asset_quantity('crypto', ticker, qty) == 'ok'


@market_bp.route('/crypto', methods=['GET', 'POST'])
def crypto():
    """Renders the main crypto market page showing top-50 by market cap (#)."""
    return available_crypto_for_letter(letter='#')


@market_bp.route('/crypto/<string:letter>', methods=['GET', 'POST'])
def available_crypto_for_letter(letter='#'):
    """Renders cryptocurrencies filtered by their starting letter, query, or top-50 (#)."""
    global _crypto_last_auto_attempt
    raw_query = letter.strip()
    is_top = raw_query in ('#', '%23', 'top', 'TOP')
    is_search = not is_top and len(raw_query) > 1
    
    clean_letter = '#' if is_top else (raw_query if is_search else raw_query.upper())
    param = {
        'letter': clean_letter,
        'search_query': raw_query if is_search else '',
        'is_search': is_search,
        'is_top': is_top,
        'crypto': []
    }
    
    if current_user.is_authenticated:
        main_symbol = current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1.0

    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
        
        # Handle crypto database reload action
        if request.form.get('reload_crypto') or (request.is_json and request.json.get('reload_crypto')):
            success = update_crypto_db()
            if is_ajax:
                return jsonify({'success': bool(success)})
            if clean_letter == '#':
                return redirect(url_for('market.crypto', reload='1' if success else '2'))
            return redirect(url_for('market.available_crypto_for_letter', letter=letter, reload='1' if success else '2'))

        # Handle adding asset to user portfolio
        if request.form.get('add_crypto') or (request.is_json and request.json.get('add_crypto')):
            handle_add_asset('add_crypto', 'crypto', param)
            if is_ajax:
                is_ok = 'success' in param
                symbol_name = param.get('success' if is_ok else 'danger', '').replace('_a', '')
                quantity = _crypto_holdings().get(symbol_name, 0) if is_ok else 0
                return jsonify({'success': is_ok, 'symbol': symbol_name,
                                'quantity': quantity, 'quantity_str': fmt_number_ru(quantity)})
            status_code = param.get('success') or param.get('danger')
            if clean_letter == '#':
                return redirect(url_for('market.crypto', status=status_code))
            return redirect(url_for('market.available_crypto_for_letter', letter=letter, status=status_code))

        # Handle setting an exact quantity (editing an asset that is already in the portfolio)
        set_symbol = request.json.get('set_crypto') if request.is_json else request.form.get('set_crypto')
        if set_symbol:
            raw_qty = request.json.get('quantity') if request.is_json else request.form.get('quantity')
            try:
                qty = float(str(raw_qty).replace(',', '.'))
            except (ValueError, TypeError):
                qty = -1.0
            ok = (current_user.is_authenticated and current_user.portfolio_id is not None
                  and qty >= 0 and _set_crypto_quantity(str(set_symbol), qty))
            quantity = _crypto_holdings().get(str(set_symbol), 0) if ok else 0
            return jsonify({'success': bool(ok), 'symbol': str(set_symbol),
                            'quantity': quantity, 'quantity_str': fmt_number_ru(quantity)})

    # Read flash status from query parameters (PRG pattern)
    reload_arg = request.args.get('reload')
    if reload_arg == '1':
        param['reload'] = 1
    elif reload_arg == '2':
        param['reload'] = 2

    status_arg = request.args.get('status')
    if status_arg:
        if '_a' in status_arg:
            param['success'] = status_arg

    sign = MAIN_SYMBOLS[main_symbol][0]
    holdings = _crypto_holdings()
    raw_cryptos = get_crypto_by_letter(clean_letter)
    for rank, crypto in enumerate(raw_cryptos, start=1):
        try:
            price_num = float(crypto['price']) / main_rate
        except (ValueError, TypeError, ZeroDivisionError):
            price_num = None
        held = holdings.get(crypto['symbol'], 0) or 0
        param['crypto'].append({
            'rank': rank,
            'symbol': crypto['symbol'],
            'name': crypto['name'],
            'title': crypto['title'] or crypto['name'],
            'price': fmt_money_ru(price_num, sign) if price_num is not None else '—',
            'price_num': price_num if price_num is not None else 0,
            'hue': ticker_hue(crypto['symbol']),
            'held': held,
            'held_str': fmt_number_ru(held) if held else '',
        })

    param['currency_code'] = main_symbol
    param['currency_sign'] = sign
    param['has_portfolio'] = current_user.is_authenticated and current_user.portfolio_id is not None
    updated_at = get_crypto_updated_at()
    param['updated_at'] = _crypto_updated_label(updated_at)
    now = datetime.now()
    is_stale = not updated_at or now - updated_at > CRYPTO_AUTO_REFRESH_AFTER
    recently_tried = _crypto_last_auto_attempt and now - _crypto_last_auto_attempt < _CRYPTO_AUTO_RETRY_AFTER
    param['auto_refresh'] = bool(is_stale and not recently_tried)
    if param['auto_refresh']:
        _crypto_last_auto_attempt = now

    return render_template('available_crypto_for_letter.html', **param)


# --- Fiat currencies ---------------------------------------------------------

_FIAT_AUTO_RETRY_AFTER = timedelta(minutes=1)
_fiat_last_auto_attempt = None


@market_bp.route('/fiat', methods=['GET', 'POST'])
def fiat():
    """All fiat currencies on one page (the ECB publishes about 30)."""
    global _fiat_last_auto_attempt

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
        if data.get('reload_fiat'):
            success = update_currencies_db(MAIN_SYMBOLS)
            if is_ajax:
                return jsonify({'success': bool(success)})
            return redirect(url_for('market.fiat', reload='1' if success else '2'))
        if data.get('add_fiat') or data.get('set_fiat'):
            return _portfolio_quantity_response('fiat', data.get('add_fiat'), data.get('set_fiat'), data)

    code, sign, _ = user_currency()
    fiats = get_all_fiats()
    reload_arg = request.args.get('reload')
    rate_date = max((f['rate_date'] for f in fiats if f['rate_date']), default=None)
    updated_at = max((f['updated_at'] for f in fiats if f['updated_at']), default=None)

    now = datetime.now()
    is_stale = not updated_at or now - updated_at > FIAT_AUTO_REFRESH_AFTER
    recently_tried = _fiat_last_auto_attempt and now - _fiat_last_auto_attempt < _FIAT_AUTO_RETRY_AFTER
    auto_refresh = bool(is_stale and not recently_tried)
    if auto_refresh:
        _fiat_last_auto_attempt = now

    param = {
        'fiats': fiat_rows(fiats, _portfolio_assets('fiat')),
        'currency_code': code,
        'currency_sign': sign,
        'has_portfolio': current_user.is_authenticated and current_user.portfolio_id is not None,
        'rate_date': f'{rate_date.day} {MONTHS_GENITIVE[rate_date.month - 1]} {rate_date.year}' if rate_date else None,
        'reload': int(reload_arg) if reload_arg in ('1', '2') else None,
        'auto_refresh': auto_refresh,
    }
    return render_template('available_fiat.html', **param)


@market_bp.route('/fiat/<string:letter>', methods=['GET', 'POST'])
def available_fiat_for_letter(letter):
    """Old per-letter pages: everything is on /fiat now."""
    return redirect(url_for('market.fiat'), code=301)
