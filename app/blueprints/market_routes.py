from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, request, url_for, jsonify, get_template_attribute
from flask_login import current_user
from app.forms import SearchTickerForm, ReloadDataForm
from app.models import db_session
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import (
    update_tickers_db, update_crypto_db, update_currencies_db,
    get_stocks_by_letter, get_stocks_by_tickers, get_crypto_by_letter, get_crypto_updated_at, get_fiat_by_letter,
    save_ticker_price
)
from app.services.api_client import fetch_quote
from app.utils import format_price

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
MAX_STOCKS_IN_PORTFOLIO = 5  # Enforced by Portfolio.set_in_dict
AUTO_REFRESH_AFTER = timedelta(minutes=15)  # /stocks refreshes the user's own stocks older than this

_STOCK_TYPES = {
    'Common Stock': 'Обыкновенные акции',
    'ETP': 'Биржевой фонд',
    'ADR': 'Депозитарные расписки (ADR)',
    'GDR': 'Депозитарные расписки (GDR)',
    'REIT': 'Фонд недвижимости (REIT)',
    'Preference': 'Привилегированные акции',
    'Closed-End Fund': 'Закрытый фонд',
    'Open-End Fund': 'Открытый фонд',
    'Equity WRT': 'Варрант',
    'Right': 'Права на акции',
    'Unit': 'Юниты',
    'MLP': 'Партнёрство (MLP)',
}

# Words kept as-is when prettifying Finnhub's UPPERCASE company names
_NAME_ACRONYMS = {'ETF', 'ETN', 'ADR', 'REIT', 'USA', 'US', 'U.S.', 'UK', 'S&P', 'NV', 'SA', 'AG', 'SE', 'LP',
                  'LLC', 'II', 'III', 'IV', 'NYSE', 'ESG', 'AI', 'MSCI', 'FTSE', 'SPDR', 'TR', 'PLC'}
_NAME_FIXES = {'PLC': 'Plc', 'CL': 'Class', 'CLASS': 'Class', 'ISHARES': 'iShares', 'JPMORGAN': 'JPMorgan'}


def _pretty_company_name(name):
    """'AIRBNB INC-CLASS A' -> 'Airbnb Inc — Class A'. Leaves already mixed-case names untouched."""
    if not name or name != name.upper():
        return name or ''
    name = name.replace('-CL ', ' — Class ').replace('-CLASS ', ' — Class ')
    words = []
    for word in name.split():
        if word in _NAME_FIXES:
            words.append(_NAME_FIXES[word])
        elif word in _NAME_ACRONYMS or any(ch.isdigit() for ch in word) \
                or (len(word) <= 3 and not any(v in word for v in 'AEIOUY')):
            words.append(word)
        else:
            words.append('-'.join(part[:1] + part[1:].lower() for part in word.split('-')))
    return ' '.join(words)


def _price_age(updated_at):
    """How long ago WE saved the price: label + freshness flags for the UI."""
    if not updated_at:
        return {'label': '', 'title': '', 'fresh': False, 'very_stale': False}
    now = datetime.now()
    diff = now - updated_at
    day = timedelta(days=1)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if diff < timedelta(minutes=1):
        label = 'только что'
    elif updated_at >= today:
        label = f'сегодня в {updated_at:%H:%M}'
    elif updated_at >= today - day:
        label = f'вчера в {updated_at:%H:%M}'
    elif diff < 30 * day:
        label = f'обновлено {diff.days} дн. назад'
    elif diff < 365 * day:
        label = f'обновлено {diff.days // 30} мес. назад'
    else:
        label = 'обновлено больше года назад'
    return {
        'label': label,
        'title': f'Цена сохранена на сайте {updated_at:%d.%m.%Y в %H:%M}. Нажмите ⟳, чтобы обновить',
        'fresh': diff < day,
        'very_stale': diff >= 30 * day,
    }


def _fmt_change(pct):
    if pct is None:
        return ''
    num = f'{abs(pct):.2f}'.replace('.', ',')
    return f'▲ +{num}%' if pct >= 0 else f'▼ −{num}%'


def _user_currency():
    """(code, sign, rate) of the current user's main currency."""
    code = current_user.main_currency if current_user.is_authenticated else 'USD'
    sign, rate = MAIN_SYMBOLS[code]
    return code, sign, (rate or 1.0)


_EXCHANGES = {'XNAS': 'NASDAQ', 'XNYS': 'NYSE', 'ARCX': 'NYSE Arca', 'XASE': 'NYSE American',
              'BATS': 'Cboe', 'OOTC': 'Внебиржевой рынок'}


def _stock_row(stock, holdings):
    """Prepares one stock for the template / AJAX response."""
    _, sign, rate = _user_currency()
    price = stock['price'] / rate if stock['price'] is not None else None
    held = holdings.get(stock['ticker'], 0) or 0
    stock_type = stock.get('type')
    return {
        'ticker': stock['ticker'],
        'title': _pretty_company_name(stock['name']) or stock['ticker'],
        'type_label': ' · '.join(filter(None, [_STOCK_TYPES.get(stock_type, stock_type or ''),
                                               _EXCHANGES.get(stock.get('mic'), stock.get('mic') or '')])),
        'is_etf': stock_type == 'ETP',
        'hue': _ticker_hue(stock['ticker']),
        'price_num': price or 0,
        'price_str': _fmt_money_ru(price, sign) if price is not None else '',
        'change_str': _fmt_change(stock.get('change_pct')),
        'change_up': (stock.get('change_pct') or 0) >= 0,
        'age': _price_age(stock.get('updated_at')),
        'needs_refresh': not stock.get('updated_at') or datetime.now() - stock['updated_at'] > AUTO_REFRESH_AFTER,
        'held': held,
        'held_str': _fmt_number_ru(held) if held else '',
        'value_str': _fmt_money_ru(price * held, sign) if price is not None and held else '',
    }


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
        row = _stock_row(stock, _portfolio_assets('stocks'))
        price_html, value_html = _render_stock_cells(row)
        return jsonify({'success': status == 'ok', 'status': status, 'price_num': row['price_num'],
                        'price_html': price_html, 'value_html': value_html})

    # Add to the portfolio (quantity is added to what is already there) or set an exact quantity
    add_ticker, set_ticker = data.get('add_stock'), data.get('set_stock')
    if add_ticker or set_ticker:
        ticker = str(add_ticker or set_ticker)
        try:
            qty = float(str(data.get('quantity', '')).replace(',', '.'))
        except (ValueError, TypeError):
            qty = None
        if add_ticker and (qty is None or qty <= 0):
            qty = 1.0
        result = 'error'
        if current_user.is_authenticated and current_user.portfolio_id is not None and qty is not None and qty >= 0:
            if add_ticker:
                qty += float(_portfolio_assets('stocks').get(ticker, 0) or 0)
            result = _set_asset_quantity('stocks', ticker, qty)
        holdings = _portfolio_assets('stocks')
        quantity = holdings.get(ticker, 0)
        return jsonify({'success': result == 'ok', 'reason': result, 'ticker': ticker,
                        'quantity': quantity, 'quantity_str': _fmt_number_ru(quantity),
                        'stocks_count': len(holdings)})
    return None


def _stocks_common_params():
    code, sign, _ = _user_currency()
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
                  'stocks': [_stock_row(s, holdings) for s in get_stocks_by_tickers(holdings.keys())]})
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
        'stocks': [_stock_row(s, holdings) for s in raw_stocks],
    })
    return render_template('available_stocks_for_letter.html', **param)


# --- Helpers for the crypto page -------------------------------------------

# Quotes older than this are reloaded automatically when someone opens /crypto
CRYPTO_AUTO_REFRESH_AFTER = timedelta(minutes=5)
# Don't retry the automatic reload more often than this (CoinGecko's keyless API allows ~10-30 calls/min)
_CRYPTO_AUTO_RETRY_AFTER = timedelta(minutes=1)
_crypto_last_auto_attempt = None


def _crypto_updated_label(updated_at):
    if not updated_at:
        return None
    if updated_at.date() == datetime.now().date():
        return f'в {updated_at:%H:%M}'
    return f'{updated_at:%d.%m} в {updated_at:%H:%M}'


def _fmt_number_ru(value, max_decimals=8):
    """Formats a number Russian-style: thin-space thousands, comma decimals, no trailing zeros."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
    text = f"{val:,.{max_decimals}f}"
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text.replace(',', ' ').replace('.', ',')


def _fmt_money_ru(value, sign):
    """Formats a price as '85 534,00 $' (2 decimals for >= 1, more precision for small prices)."""
    try:
        val = float(value)
    except (ValueError, TypeError):
        return '—'
    if abs(val) >= 1 or val == 0:
        num = f"{val:,.2f}".replace(',', ' ').replace('.', ',')
    else:
        num = format_price(val).replace('.', ',')
    return f"{num} {sign}"


def _ticker_hue(symbol):
    """Stable hue (0-359) per ticker for the coloured monogram."""
    return (sum(ord(ch) * (i + 7) for i, ch in enumerate(symbol)) * 37) % 360


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
                                'quantity': quantity, 'quantity_str': _fmt_number_ru(quantity)})
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
                            'quantity': quantity, 'quantity_str': _fmt_number_ru(quantity)})

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
            'price': _fmt_money_ru(price_num, sign) if price_num is not None else '—',
            'price_num': price_num if price_num is not None else 0,
            'hue': _ticker_hue(crypto['symbol']),
            'held': held,
            'held_str': _fmt_number_ru(held) if held else '',
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


@market_bp.route('/fiat', methods=['GET', 'POST'])
def fiat():
    """Renders the main fiat currencies market page."""
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {
        'form': form,
        'form2': form2
    }

    if form.submit1.data:
        if 'all' not in form.ticker.data and 'main' not in form.ticker.data:
            return redirect(f'fiat/{form.ticker.data}')
    if form2.submit2.data:
        if update_currencies_db(MAIN_SYMBOLS):
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_fiat.html', **param)


@market_bp.route('/fiat/<string:letter>', methods=['GET', 'POST'])
def available_fiat_for_letter(letter):
    """Renders fiat currencies filtered by their starting letter."""
    param = {'letter': letter.upper(), 'fiats': []}
    
    if current_user.is_authenticated:
        main_symbol = current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1.0

    raw_fiats = get_fiat_by_letter(letter, MAIN_SYMBOLS.keys())
    for fiat in raw_fiats:
        price_val = f"{format_price(float(fiat['price']) / main_rate)}{MAIN_SYMBOLS[main_symbol][0]}"
        param['fiats'].append({'symbol': fiat['symbol'], 'name': fiat['name'], 'price': price_val})

    if request.method == 'POST':
        handle_add_asset('add_fiat', 'fiat', param)

    return render_template('available_fiat_for_letter.html', **param)
