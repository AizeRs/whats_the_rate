"""Turns stored assets into rows for the templates (market and portfolio pages)."""
from datetime import datetime, timedelta
from app.services.symbols import MAIN_SYMBOLS
from app.formatting import (
    pretty_company_name, STOCK_TYPES, EXCHANGES, price_age, fmt_change, user_currency,
    fmt_number_ru, fmt_money_ru, ticker_hue, FIAT_INFO, fiat_unit, fmt_fiat_price
)

MAX_STOCKS_IN_PORTFOLIO = 5  # Enforced by Portfolio.set_in_dict

# Prices older than this are reloaded automatically when a page with them is opened
STOCK_AUTO_REFRESH_AFTER = timedelta(minutes=15)  # Finnhub: one request per ticker
CRYPTO_AUTO_REFRESH_AFTER = timedelta(minutes=5)  # CoinGecko: one request for all coins
FIAT_AUTO_REFRESH_AFTER = timedelta(hours=1)  # ECB publishes rates once per working day

# The currencies users can display prices in go first on /fiat
FIAT_FIRST = ['USD', 'EUR', 'GBP', 'JPY', 'CHF']


def stock_row(stock, holdings):
    """Prepares one stock for the template / AJAX response."""
    _, sign, rate = user_currency()
    price = stock['price'] / rate if stock['price'] is not None else None
    held = holdings.get(stock['ticker'], 0) or 0
    stock_type = stock.get('type')
    return {
        'ticker': stock['ticker'],
        'title': pretty_company_name(stock['name']) or stock['ticker'],
        'type_label': ' · '.join(filter(None, [STOCK_TYPES.get(stock_type, stock_type or ''),
                                               EXCHANGES.get(stock.get('mic'), stock.get('mic') or '')])),
        'is_etf': stock_type == 'ETP',
        'hue': ticker_hue(stock['ticker']),
        'price_num': price or 0,
        'price_str': fmt_money_ru(price, sign) if price is not None else '',
        'change_str': fmt_change(stock.get('change_pct')),
        'change_up': (stock.get('change_pct') or 0) >= 0,
        'age': price_age(stock.get('updated_at')),
        'needs_refresh': not stock.get('updated_at') or datetime.now() - stock['updated_at'] > STOCK_AUTO_REFRESH_AFTER,
        'held': held,
        'held_str': fmt_number_ru(held) if held else '',
        'value_str': fmt_money_ru(price * held, sign) if price is not None and held else '',
    }


def fiat_rows(fiats, holdings):
    code, sign, _ = user_currency()
    by_code = {f['code']: f for f in fiats}
    base = by_code.get(code)
    base_price = base['price'] if base and base['price'] else (MAIN_SYMBOLS[code][1] or 1.0)
    base_change = (base['change_pct'] or 0) if base else 0

    def order(f):
        return (FIAT_FIRST.index(f['code']) if f['code'] in FIAT_FIRST else len(FIAT_FIRST), f['code'])

    rows = []
    for f in sorted(fiats, key=order):
        if not f['price']:
            continue
        ru, fiat_sign = FIAT_INFO.get(f['code'], (f['name'], f['code']))
        price = f['price'] / base_price
        unit = fiat_unit(price)
        change = None
        if f['change_pct'] is not None:
            # Change in the user's currency: both prices moved against USD
            change = ((1 + f['change_pct'] / 100) / (1 + base_change / 100) - 1) * 100
        held = holdings.get(f['code'], 0) or 0
        rows.append({
            'code': f['code'],
            'title': ru,
            'name': f['name'],
            'sign': fiat_sign,
            'hue': ticker_hue(f['code']),
            'is_base': f['code'] == code,
            'price_num': price,
            'price_str': fmt_fiat_price(price * unit, sign),
            'unit': unit,
            'unit_str': f"{fmt_number_ru(unit)} {f['code']}",
            'change_str': fmt_change(change) if change is not None and abs(change) >= 0.005 else ('0,00%' if change is not None else ''),
            'change_up': change is not None and change > 0,
            'change_down': change is not None and change < 0,
            'change_pct': change,
            'held': held,
            'held_str': fmt_number_ru(held, 2) if held else '',
            'search': ' '.join([f['code'], ru, f['name'] or '']).lower(),
        })
    return rows
