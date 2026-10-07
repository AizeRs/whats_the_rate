from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, url_for, jsonify
from flask_login import current_user
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import (
    update_crypto_db, update_currencies_db, save_ticker_price,
    get_stocks_by_tickers, get_crypto_by_symbols, get_all_fiats
)
from app.services.api_client import fetch_quote
from app.formatting import price_age, fmt_money_ru, fmt_number_ru, ticker_hue, user_currency, MONTHS_GENITIVE
from app.presenters import (
    stock_row, fiat_rows, MAX_STOCKS_IN_PORTFOLIO, STOCK_AUTO_REFRESH_AFTER, CRYPTO_AUTO_REFRESH_AFTER,
    FIAT_AUTO_REFRESH_AFTER
)

portfolio_bp = Blueprint('portfolio', __name__)

_CATEGORIES = [
    # kind, title, colour, unit, market page, "add" link text
    ('stocks', 'Акции', '#3b82f6', 'шт.', 'market.stocks', 'Добавить акции →'),
    ('crypto', 'Криптовалюты', '#f0a742', None, 'market.crypto', 'Добавить криптовалюту →'),
    ('fiat', 'Фиатные валюты', '#c0c1ff', None, 'market.fiat', 'Добавить валюту →'),
]

# Don't retry the automatic price reload of one portfolio more often than this
_AUTO_RETRY_AFTER = timedelta(minutes=1)
_last_auto_reload = {}


def _share_str(part, total):
    if not total:
        return ''
    pct = part / total * 100
    return (f'{pct:.0f}%' if pct >= 10 else f'{pct:.1f}%').replace('.', ',')


def _build_rows(data):
    """Rows of the three tables with prices in the viewer's currency."""
    _, sign, rate = user_currency()
    rows = {kind: [] for kind, *_ in _CATEGORIES}

    # Stocks
    stocks = data.get('stocks', {})
    for stock in get_stocks_by_tickers(stocks.keys()):
        r = stock_row(stock, stocks)
        rows['stocks'].append({
            'code': r['ticker'], 'title': r['title'], 'mono': r['ticker'][:4], 'square': True, 'hue': r['hue'],
            'qty': r['held'], 'qty_str': r['held_str'], 'unit': 'шт.',
            'price_str': r['price_str'], 'value': r['price_num'] * r['held'],
            'change_str': r['change_str'] if r['age']['fresh'] else '', 'change_dir': 'up' if r['change_up'] else 'down',
            'age': r['age'],
        })

    # Crypto
    cryptos = data.get('crypto', {})
    for symbol, coin in sorted(get_crypto_by_symbols(cryptos.keys()).items()):
        qty = cryptos.get(symbol, 0) or 0
        price = coin['price'] / rate if coin['price'] is not None else None
        rows['crypto'].append({
            'code': symbol, 'title': coin['title'] or coin['name'], 'mono': symbol[:1], 'square': False,
            'hue': ticker_hue(symbol), 'qty': qty, 'qty_str': fmt_number_ru(qty), 'unit': symbol,
            'price_str': fmt_money_ru(price, sign) if price is not None else '', 'value': (price or 0) * qty,
            'change_str': '', 'change_dir': 'flat', 'age': price_age(coin['updated_at']),
        })

    # Fiat
    fiats = data.get('fiat', {})
    all_fiats = get_all_fiats()
    rate_date = max((f['rate_date'] for f in all_fiats if f['rate_date']), default=None)
    ecb_label = f'ЕЦБ, {rate_date.day} {MONTHS_GENITIVE[rate_date.month - 1][:3]}' if rate_date else ''
    for f in fiat_rows(all_fiats, fiats):
        if not f['held']:
            continue
        rows['fiat'].append({
            'code': f['code'], 'title': f['title'], 'mono': f['sign'], 'square': False, 'hue': f['hue'],
            'qty': f['held'], 'qty_str': f['held_str'], 'unit': f['code'],
            'price_str': (f"{f['unit_str']} = " if f['unit'] > 1 else '') + f['price_str'],
            'value': f['price_num'] * f['held'],
            'change_str': f['change_str'],
            'change_dir': 'up' if f['change_up'] else ('down' if f['change_down'] else 'flat'),
            'age': {'label': ecb_label, 'title': '', 'fresh': True, 'very_stale': False},
        })
    return rows


def _body_params(data):
    """Everything _portfolio_body.html needs."""
    code, sign, _ = user_currency()
    rows = _build_rows(data)
    total = sum(r['value'] for kind_rows in rows.values() for r in kind_rows)
    categories = []
    for kind, title, color, unit, endpoint, add_label in _CATEGORIES:
        kind_rows = rows[kind]
        cat_sum = sum(r['value'] for r in kind_rows)
        for r in kind_rows:
            r['value_str'] = fmt_money_ru(r['value'], sign) if r['price_str'] else '—'
            r['share_str'] = _share_str(r['value'], total)
        categories.append({
            'kind': kind, 'title': title, 'color': color, 'rows': kind_rows,
            'sum_str': fmt_money_ru(cat_sum, sign), 'share_str': _share_str(cat_sum, total),
            'pct': f'{cat_sum / total * 100:.2f}' if total else '0',
            'url': url_for(endpoint), 'add_label': add_label,
        })
    return {
        'categories': categories,
        'is_empty': not any(rows.values()),
        'total_str': fmt_money_ru(total, sign),
        'currency_code': code,
        'stocks_full': len(data.get('stocks', {})) >= MAX_STOCKS_IN_PORTFOLIO,
    }


def _stale_parts(data):
    """What needs an automatic reload: stale stock tickers, and whether crypto / fiat are stale."""
    now = datetime.now()
    stale_stocks = [s['ticker'] for s in get_stocks_by_tickers(data.get('stocks', {}).keys())
                    if not s['updated_at'] or now - s['updated_at'] > STOCK_AUTO_REFRESH_AFTER]
    crypto_times = [c['updated_at'] for c in get_crypto_by_symbols(data.get('crypto', {}).keys()).values()]
    crypto_stale = bool(crypto_times) and any(not t or now - t > CRYPTO_AUTO_REFRESH_AFTER for t in crypto_times)
    fiat_stale = False
    if data.get('fiat'):
        fiat_times = [f['updated_at'] for f in get_all_fiats() if f['updated_at']]
        fiat_stale = not fiat_times or now - max(fiat_times) > FIAT_AUTO_REFRESH_AFTER
    return stale_stocks, crypto_stale, fiat_stale


def _reload_prices(data, stock_tickers, crypto, fiat):
    """Reloads prices; returns a list of problems for the message shown to the user."""
    problems = []
    for ticker in stock_tickers:
        status, quote = fetch_quote(ticker)
        if status == 'ok':
            save_ticker_price(ticker, quote['c'], quote.get('dp'))
        elif status == 'limit':
            problems.append('Finnhub временно ограничил запросы — часть цен акций не обновилась.')
            break
    if crypto and not update_crypto_db():
        problems.append('Не удалось обновить курсы криптовалют.')
    if fiat and not update_currencies_db(MAIN_SYMBOLS):
        problems.append('Не удалось обновить курсы валют.')
    return problems


def _set_quantity(pf, kind, code, qty):
    if float(qty).is_integer():
        qty = int(qty)
    if pf.set_in_dict(kind, code, qty) == 'Too Many Stocks Error':
        return False
    return True


@portfolio_bp.route('/portfolios/<username>', methods=['GET', 'POST'])
def portfolios_username(username):
    """Portfolio page; the owner edits quantities and reloads prices via AJAX."""
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.username == username).first()
        pf = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).first() if user else None
        if not pf:
            return render_template('portfolios.html', not_found=True), 404

        is_owner = current_user.is_authenticated and current_user.id == user.id
        if pf.isprivate and not is_owner:
            return render_template('portfolios.html', no_access=True), 403

        data = pf.get_dict()

        if request.method == 'POST':
            if not is_owner:
                return jsonify({'success': False}), 403
            body = request.get_json(silent=True) or {}
            problems = []

            if body.get('reload'):
                if body['reload'] == 'auto':
                    stale_stocks, crypto_stale, fiat_stale = _stale_parts(data)
                    problems = _reload_prices(data, stale_stocks, crypto_stale, fiat_stale)
                else:
                    problems = _reload_prices(data, list(data.get('stocks', {})),
                                              bool(data.get('crypto')), bool(data.get('fiat')))

            elif body.get('kind') in ('stocks', 'crypto', 'fiat') and body.get('code'):
                try:
                    qty = float(str(body.get('quantity')).replace(' ', '').replace(',', '.'))
                except (ValueError, TypeError):
                    qty = -1
                if qty < 0:
                    return jsonify({'success': False, 'message': 'Введите число не меньше нуля.'})
                if not _set_quantity(pf, body['kind'], str(body['code']), qty):
                    return jsonify({'success': False, 'message': 'В портфеле может быть не больше 5 акций.'})
                db_sess.commit()
                data = pf.get_dict()

            return jsonify({
                'success': not problems,
                'message': ' '.join(problems),
                'html': render_template('_portfolio_body.html', is_owner=True, **_body_params(data)),
            })

        auto_reload = False
        if is_owner:
            stale_stocks, crypto_stale, fiat_stale = _stale_parts(data)
            last = _last_auto_reload.get(user.id)
            if (stale_stocks or crypto_stale or fiat_stale) and not (last and datetime.now() - last < _AUTO_RETRY_AFTER):
                auto_reload = True
                _last_auto_reload[user.id] = datetime.now()

        return render_template(
            'portfolios.html',
            username=username,
            is_owner=is_owner,
            is_private=bool(pf.isprivate),
            share_url=url_for('portfolio.portfolios_username', username=username, _external=True),
            auto_reload=auto_reload,
            **_body_params(data),
        )
