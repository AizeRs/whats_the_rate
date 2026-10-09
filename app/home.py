"""Data for the home page: a quotes table for three markets, the biggest movers and the ticker tape."""
from datetime import datetime, timedelta
from flask import url_for
from app.services.data_service import (
    get_top_crypto, get_stocks_by_tickers, get_all_fiats, ensure_stocks, get_fiat_history, get_crypto_updated_at
)
from app.formatting import (
    price_age, fmt_change, fmt_money_ru, fmt_big_money, ticker_hue, user_currency, to_user_tz, MONTHS_GENITIVE
)
from app.presenters import stock_row, fiat_rows, CRYPTO_AUTO_REFRESH_AFTER, FIAT_AUTO_REFRESH_AFTER

CRYPTO_ROWS = 8
# Currencies in the table, in this order (the viewer's own currency is skipped)
FIATS = ['USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CNY', 'CAD']
FIAT_ROWS = 6
# Stocks in the table; their prices are reloaded in the background when they're older than the usual limit
STOCKS = {  # ticker: (name, type, exchange) — used only if the ticker list hasn't been loaded yet
    'AAPL': ('APPLE INC', 'Common Stock', 'XNAS'),
    'NVDA': ('NVIDIA CORP', 'Common Stock', 'XNAS'),
    'MSFT': ('MICROSOFT CORP', 'Common Stock', 'XNAS'),
    'TSLA': ('TESLA INC', 'Common Stock', 'XNAS'),
    'AMZN': ('AMAZON.COM INC', 'Common Stock', 'XNAS'),
}
# Market caps change slowly: reload one at most once a day (per worker; after a restart it's loaded again)
MARKET_CAP_MAX_AGE = timedelta(days=1)
_cap_loaded_at = {}
# Don't retry the automatic reload of one ticker more often than this (Finnhub: ~60 requests/min for the whole site)
STOCK_RETRY_AFTER = timedelta(minutes=1)
_stock_attempts = {}
STABLECOINS = {'USDT', 'USDC', 'DAI', 'FDUSD', 'USDE', 'TUSD', 'PYUSD', 'USDS'}

SPARK_W, SPARK_H = 96, 28


def _change(pct):
    """(label, direction) for a change in %."""
    if pct is None:
        return '', 'flat'
    if abs(pct) < 0.005:
        return '0,00%', 'flat'
    return fmt_change(pct), 'up' if pct > 0 else 'down'


def _spark_points(values):
    """SVG polyline points for a small sparkline, or '' when there's nothing to draw."""
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return ''
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = SPARK_W / (len(values) - 1)
    return ' '.join(f'{i * step:.1f},{SPARK_H - 2 - (v - lo) / span * (SPARK_H - 4):.1f}' for i, v in enumerate(values))


def _row(**kw):
    row = {'unit': '', 'cap': '', 'spark': '', 'week': '', 'week_dir': 'flat', 'refresh': '', 'note': '',
           'change_pct': None}
    row.update(kw)
    return row


def _crypto_rows():
    _, sign, rate = user_currency()
    rows = []
    for rank, c in enumerate(get_top_crypto(CRYPTO_ROWS), start=1):
        fresh = price_age(c['updated_at'])['fresh']
        change, direction = _change(c['change_pct'] if fresh else None)
        week, week_dir = _change(c['change_7d_pct'] if fresh else None)
        rows.append(_row(
            rank=rank, title=c['title'], code=c['symbol'], mono=c['symbol'][:1], square=False, hue=ticker_hue(c['symbol']),
            price_str=fmt_money_ru(c['price'] / rate, sign), change_str=change, dir=direction,
            change_pct=c['change_pct'] if fresh else None,
            week=week, week_dir=week_dir, spark=_spark_points(c['sparkline']) if fresh else '',
            cap=fmt_big_money(c['market_cap'] / rate if c['market_cap'] else None, sign),
        ))
    return rows


def stock_home_row(stock):
    """One stock row; also used by the AJAX price refresh."""
    _, sign, rate = user_currency()
    r = stock_row(stock, {})
    fresh = r['age']['fresh']
    change, direction = _change(stock['change_pct'] if fresh else None)
    return _row(
        rank=list(STOCKS).index(r['ticker']) + 1 if r['ticker'] in STOCKS else '',
        title=r['title'], code=r['ticker'], mono=r['ticker'][:4], square=True, hue=r['hue'],
        price_str=r['price_str'] or '—', change_str=change, dir=direction,
        change_pct=stock['change_pct'] if fresh else None,
        note='' if change else r['age']['label'], stale=r['needs_refresh'],
        cap=fmt_big_money(stock['market_cap'] / rate if stock.get('market_cap') else None, sign),
    )


def _stock_rows():
    now = datetime.now()
    by_ticker = {s['ticker']: s for s in get_stocks_by_tickers(STOCKS)}
    if len(by_ticker) < len(STOCKS):
        ensure_stocks(STOCKS)
        by_ticker = {s['ticker']: s for s in get_stocks_by_tickers(STOCKS)}
    rows = []
    for ticker in STOCKS:
        stock = by_ticker.get(ticker)
        if not stock:
            continue
        row = stock_home_row(stock)
        last = _stock_attempts.get(ticker)
        if (row['stale'] or market_cap_is_stale(stock)) and not (last and now - last < STOCK_RETRY_AFTER):
            _stock_attempts[ticker] = now
            row['refresh'] = ticker
            if not row['change_str']:
                row['note'] = 'обновляется…'
        rows.append(row)
    return rows


def market_cap_is_stale(stock):
    loaded = _cap_loaded_at.get(stock['ticker'])
    return not stock.get('market_cap') or not loaded or datetime.now() - loaded > MARKET_CAP_MAX_AGE


def market_cap_loaded(ticker):
    _cap_loaded_at[ticker] = datetime.now()


def _per_usd(rates, code):
    """Units of a currency per 1 USD in one ECB fixing (USD itself isn't listed: it's the base)."""
    return 1.0 if code == 'USD' else rates.get(code)


def _fiat_rows(fiats):
    code, _, _ = user_currency()
    by_code = {f['code']: f for f in fiat_rows(fiats, {})}
    history = get_fiat_history()
    days = sorted(history)
    rows = []
    for fiat_code in FIATS:
        f = by_code.get(fiat_code)
        if not f or f['is_base'] or len(rows) == FIAT_ROWS:
            continue
        change, direction = _change(f['change_pct'])
        # Price of one unit in the viewer's currency for each ECB fixing
        series = []
        for d in days:
            base, this = _per_usd(history[d], code), _per_usd(history[d], fiat_code)
            if base and this:
                series.append(base / this)
        week_pct = (series[-1] / series[0] - 1) * 100 if len(series) > 1 and series[0] else None
        week, week_dir = _change(week_pct)
        rows.append(_row(
            rank=len(rows) + 1, title=f['title'], code=fiat_code, mono=f['sign'], square=False, hue=f['hue'],
            unit=f'{f["unit_str"]} = ' if f['unit'] > 1 else '', price_str=f['price_str'],
            change_str=change, dir=direction, change_pct=f['change_pct'],
            week=week, week_dir=week_dir, spark=_spark_points(series),
        ))
    return rows


def _movers(rows, count=3):
    """Biggest risers and fallers among the rows on the page."""
    moving = [r for r in rows if r['change_pct'] is not None and abs(r['change_pct']) >= 0.005]
    up = sorted((r for r in moving if r['change_pct'] > 0), key=lambda r: -r['change_pct'])[:count]
    down = sorted((r for r in moving if r['change_pct'] < 0), key=lambda r: r['change_pct'])[:count]
    return {'up': up, 'down': down}


def _tape(crypto, stocks, fiat):
    """Ticker tape: a few big coins (no stablecoins), all the stocks and the main currencies."""
    coins = [r for r in crypto if r['code'] not in STABLECOINS][:4]
    return [r for r in coins + stocks + fiat[:3] if r['price_str'] and r['price_str'] != '—']


def _time_label(moment):
    if not moment:
        return ''
    shown, today = to_user_tz(moment), to_user_tz(datetime.now())
    return f'в {shown:%H:%M}' if shown.date() == today.date() else f'{shown:%d.%m} в {shown:%H:%M}'


def home_markets():
    crypto = _crypto_rows()
    stocks = _stock_rows()
    fiats = get_all_fiats()
    fiat = _fiat_rows(fiats)

    crypto_updated = get_crypto_updated_at()
    stock_times = [s['updated_at'] for s in get_stocks_by_tickers(STOCKS) if s['updated_at']]
    rate_date = max((f['rate_date'] for f in fiats if f['rate_date']), default=None)
    fiat_updated = max((f['updated_at'] for f in fiats if f['updated_at']), default=None)
    now = datetime.now()

    tabs = [
        {'key': 'crypto', 'label': 'Криптовалюты', 'change_head': '24 часа', 'week': True, 'cap': True,
         'note': f'CoinGecko · обновлено {_time_label(crypto_updated)}' if crypto_updated else 'CoinGecko',
         'rows': crypto, 'url': url_for('market.crypto'), 'link': 'Все криптовалюты'},
        {'key': 'stocks', 'label': 'Акции', 'change_head': 'За день', 'week': False, 'cap': True,
         'note': f'биржи США · обновлено {_time_label(max(stock_times))}' if stock_times else 'биржи США',
         'rows': stocks, 'url': url_for('market.stocks'), 'link': 'Все акции'},
        {'key': 'fiat', 'label': 'Валюты', 'change_head': 'За день', 'week': True, 'cap': False,
         'note': f'курсы ЕЦБ на {rate_date.day} {MONTHS_GENITIVE[rate_date.month - 1]}' if rate_date else 'курсы ЕЦБ',
         'rows': fiat, 'url': url_for('market.fiat'), 'link': 'Все валюты'},
    ]
    return {
        'tabs': tabs,
        'movers': _movers(crypto + stocks + fiat),
        'tape': _tape(crypto, stocks, fiat),
        # Same thresholds as on the market pages: the page asks the server to reload old quotes
        'crypto_stale': not crypto_updated or now - crypto_updated > CRYPTO_AUTO_REFRESH_AFTER,
        'fiat_stale': not fiat_updated or now - fiat_updated > FIAT_AUTO_REFRESH_AFTER,
    }


def greeting():
    """Greeting by the time of day in the visitor's timezone (the browser sends it in the 'tz' cookie)."""
    hour = to_user_tz(datetime.now()).hour
    if 5 <= hour < 12:
        return 'Доброе утро'
    if 12 <= hour < 18:
        return 'Добрый день'
    if 18 <= hour < 23:
        return 'Добрый вечер'
    return 'Доброй ночи'
