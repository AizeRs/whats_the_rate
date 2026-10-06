from datetime import datetime
from flask import Blueprint, render_template, redirect, request, url_for, jsonify
from flask_login import current_user
from app.forms import SearchTickerForm, ReloadDataForm
from app.models import db_session
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import (
    update_tickers_db, update_crypto_db, update_currencies_db,
    get_stocks_by_letter, get_crypto_by_letter, get_fiat_by_letter,
    save_ticker_price
)
from app.services.api_client import ticker_price
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
@market_bp.route('/stocks', methods=['GET', 'POST'])
def stocks():
    """Renders the main stocks market page."""
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {
        'form': form,
        'form2': form2,
        'alphabet': ('abcdefg', 'hijklmn', 'opqrstu', 'vwxyz')
    }

    if form.submit1.data:
        return redirect(f'stocks/{form.ticker.data.upper()}')
    if form2.submit2.data:
        if update_tickers_db():
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_stocks.html', **param)


@market_bp.route('/stocks/<string:letter>', methods=['GET', 'POST'])
def available_stocks_for_letter(letter):
    """Renders stocks filtered by their starting letter."""
    param = {'letter': letter.upper(), 'stocks': []}
    
    if current_user.is_authenticated:
        main_symbol = current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1.0

    if request.method == 'POST':
        if request.form.get('reload_rate'):
            ticker = request.form.get('reload_rate').split()[-1]
            price_data = ticker_price(ticker)
            if price_data and price_data[0]:
                param['success'] = f'{ticker}_r'
                save_ticker_price(ticker, price_data[0])
            else:
                param['danger'] = f'{ticker}_r'
                
        handle_add_asset('add_stock', 'stocks', param)

    raw_stocks = get_stocks_by_letter(letter)
    for stock in raw_stocks:
        price_val = stock['price']
        if price_val != 'No price data':
            price_val = f"{format_price(float(price_val) / main_rate)}{MAIN_SYMBOLS[main_symbol][0]}"
        param['stocks'].append({'ticker': stock['ticker'], 'stock': stock['stock'], 'price': price_val})
        
    return render_template('available_stocks_for_letter.html', **param)


# --- Helpers for the crypto page -------------------------------------------

# Time of the last successful quotes reload in this process (shown on the crypto page).
_crypto_updated_at = None


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


def _crypto_holdings():
    """Returns the crypto part of the current user's portfolio as {SYMBOL: quantity}."""
    if not (current_user.is_authenticated and current_user.portfolio_id is not None):
        return {}
    with db_session.create_session() as db_sess:
        pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
        if not pf:
            return {}
        return dict(pf.get_dict().get('crypto', {}))


def _set_crypto_quantity(ticker, qty):
    """Sets an exact quantity of a crypto asset in the user's portfolio (0 removes it)."""
    if qty.is_integer():
        qty = int(qty)
    with db_session.create_session() as db_sess:
        pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
        if not pf:
            return False
        pf.set_in_dict('crypto', ticker, qty)
        db_sess.commit()
        return True


@market_bp.route('/crypto', methods=['GET', 'POST'])
def crypto():
    """Renders the main crypto market page showing top-50 by market cap (#)."""
    return available_crypto_for_letter(letter='#')


@market_bp.route('/crypto/<string:letter>', methods=['GET', 'POST'])
def available_crypto_for_letter(letter='#'):
    """Renders cryptocurrencies filtered by their starting letter, query, or top-50 (#)."""
    global _crypto_updated_at
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
            if success:
                _crypto_updated_at = datetime.now()
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
    param['updated_at'] = _crypto_updated_at.strftime('%H:%M') if _crypto_updated_at else None

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
