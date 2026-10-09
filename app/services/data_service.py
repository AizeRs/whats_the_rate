import os
from datetime import datetime
from sqlalchemy import or_, func, case
from app.models.db_session import create_session
from app.models.rates import StockRate, CryptoRate, FiatRate
import json
from datetime import timedelta
from .api_client import fetch_crypto_data, fetch_fiat_data, fetch_tickers_data, fetch_fiat_history

def update_crypto_db():
    """Updates the database with the latest cryptocurrency prices."""
    success, data = fetch_crypto_data()
    if not success:
        return False
    try:
        now = datetime.now()
        with create_session() as session:
            for coin in data:
                crypto = session.query(CryptoRate).filter(CryptoRate.coin_id == coin['coin_id']).first()
                if not crypto:
                    crypto = CryptoRate(symbol=coin['symbol'], coin_id=coin['coin_id'])
                    session.add(crypto)
                crypto.price = float(coin['price'])
                crypto.change_pct = coin['change_pct']
                crypto.change_7d_pct = coin['change_7d_pct']
                crypto.market_cap = coin['market_cap']
                crypto.sparkline = json.dumps(coin['sparkline']) if coin['sparkline'] else None
                crypto.name = coin['name'] or None
                crypto.price_updated_at = now
            session.commit()
        return True
    except Exception as e:
        print(f"Error writing crypto to db: {e}")
        return False

def update_currencies_db(main_symbols_dict):
    """Updates the database with the latest fiat currency prices."""
    success, names, prices, previous_prices, rate_date = fetch_fiat_data()
    if not success:
        return False
    try:
        now = datetime.now()
        with create_session() as session:
            for currency, name in names.items():
                if currency in prices:
                    rate = 1 / float(prices[currency])
                    fiat = session.query(FiatRate).filter(FiatRate.symbol == currency).first()
                    if not fiat:
                        fiat = FiatRate(symbol=currency, name=name)
                        session.add(fiat)
                    fiat.price = rate
                    # Rates are units per 1 USD, so the USD price of one unit changes by previous / current
                    previous = previous_prices.get(currency)
                    fiat.change_pct = (float(previous) / float(prices[currency]) - 1) * 100 if previous else None
                    fiat.rate_date = rate_date
                    fiat.updated_at = now
                    if currency in main_symbols_dict:
                        main_symbols_dict[currency] = (main_symbols_dict[currency][0], rate)
            session.commit()
            return True
    except Exception as e:
        print(f"Error writing currencies to db: {e}")
        return False

def update_tickers_db():
    """Updates the database with the latest stock tickers."""
    try:
        my_list = fetch_tickers_data()
    except Exception:
        return False
    
    if not my_list:
        return False
        
    try:
        with create_session() as session:
            existing = {s.ticker: s for s in session.query(StockRate).all()}
            for ticker_symbol, description, stock_type, mic in my_list:
                stock = existing.get(ticker_symbol)
                if not stock:
                    stock = StockRate(ticker=ticker_symbol, name=description)
                    session.add(stock)
                    existing[ticker_symbol] = stock
                stock.type = stock_type
                stock.mic = mic
            session.commit()
            return True
    except Exception as e:
        print(f"Error writing tickers to db: {e}")
        return False

def save_ticker_price(ticker, price, change_pct=None):
    """Saves a new price (and daily change, %) for a stock ticker and remembers when we saved it."""
    try:
        with create_session() as session:
            stock = session.query(StockRate).filter(StockRate.ticker == ticker).first()
            if stock:
                stock.price = price
                stock.change_pct = change_pct
                stock.price_updated_at = datetime.now()
                session.commit()
                return True
            return False
    except Exception as e:
        print(f"Error saving ticker price to db: {e}")
        return False

def _stock_dict(r):
    return {'ticker': r.ticker, 'name': r.name, 'type': r.type, 'mic': r.mic, 'price': r.price,
            'change_pct': r.change_pct, 'updated_at': r.price_updated_at, 'market_cap': r.market_cap}


def get_stocks_by_letter(query, page=1, per_page=50):
    """Returns (stocks, has_next): one page of stocks — listed before OTC, priced first, then by ticker.

    A single character filters by the first letter of the ticker; a longer query matches
    the beginning of the ticker or any part of the company name.
    """
    stocks, has_next = [], False
    try:
        with create_session() as session:
            query = str(query).strip()
            if len(query) == 1:
                q = session.query(StockRate).filter(StockRate.ticker.startswith(query.upper()))
            else:
                q = session.query(StockRate).filter(or_(
                    StockRate.ticker.startswith(query.upper()),
                    StockRate.name.ilike(f'%{query}%')
                ))
            # Finnhub gives no popularity data, so: exchange-listed first, then over-the-counter (OOTC),
            # then tickers without an exchange (no longer in Finnhub's list, e.g. delisted);
            # inside each group stocks with a known price first, then alphabetically
            listing_rank = case((StockRate.mic.is_(None), 2), (StockRate.mic == 'OOTC', 1), else_=0)
            results = q.order_by(listing_rank, StockRate.price.is_(None).asc(), StockRate.ticker.asc()) \
                .offset((page - 1) * per_page).limit(per_page + 1).all()
            has_next = len(results) > per_page
            stocks = [_stock_dict(r) for r in results[:per_page]]
    except Exception as e:
        print(e)
    return stocks, has_next


def get_stocks_by_tickers(tickers):
    """Returns stocks for the given tickers, sorted by ticker."""
    if not tickers:
        return []
    try:
        with create_session() as session:
            results = session.query(StockRate).filter(StockRate.ticker.in_(list(tickers))) \
                .order_by(StockRate.ticker.asc()).all()
            return [_stock_dict(r) for r in results]
    except Exception as e:
        print(e)
        return []

def get_crypto_updated_at():
    """When the crypto quotes were last loaded (None if never)."""
    try:
        with create_session() as session:
            return session.query(func.max(CryptoRate.price_updated_at)).scalar()
    except Exception as e:
        print(e)
        return None

def get_top_crypto(limit=8):
    """The biggest coins by market cap (ids follow CoinGecko's order) — for the home page."""
    try:
        with create_session() as session:
            results = session.query(CryptoRate).filter(CryptoRate.price.isnot(None)) \
                .order_by(CryptoRate.id.asc()).limit(limit).all()
            return [{'symbol': r.symbol, 'title': r.name or r.coin_id, 'price': r.price,
                     'change_pct': r.change_pct, 'change_7d_pct': r.change_7d_pct, 'market_cap': r.market_cap,
                     'sparkline': json.loads(r.sparkline) if r.sparkline else [],
                     'updated_at': r.price_updated_at} for r in results]
    except Exception as e:
        print(e)
        return []


def save_stock_market_cap(ticker, market_cap):
    try:
        with create_session() as session:
            stock = session.query(StockRate).filter(StockRate.ticker == ticker).first()
            if stock:
                stock.market_cap = market_cap
                session.commit()
    except Exception as e:
        print(f"Error saving market cap: {e}")


# ECB fixings for the home page sparklines: change once a day, so one request per hour per worker is plenty
_FIAT_HISTORY_TTL = timedelta(hours=1)
_fiat_history_cache = {'at': None, 'data': {}}


def get_fiat_history():
    """{date: {CODE: units per 1 USD}} for the last ~week, cached."""
    now = datetime.now()
    cached_at = _fiat_history_cache['at']
    if cached_at is None or now - cached_at > _FIAT_HISTORY_TTL or not _fiat_history_cache['data']:
        data = fetch_fiat_history()
        if data or cached_at is None:
            _fiat_history_cache['data'] = data
        _fiat_history_cache['at'] = now
    return _fiat_history_cache['data']


def ensure_stocks(stocks):
    """Adds the given stocks ({ticker: (name, type, mic)}) if the ticker list hasn't been loaded yet."""
    try:
        with create_session() as session:
            existing = {t for (t,) in session.query(StockRate.ticker).filter(StockRate.ticker.in_(list(stocks)))}
            for ticker, (name, stock_type, mic) in stocks.items():
                if ticker not in existing:
                    session.add(StockRate(ticker=ticker, name=name, type=stock_type, mic=mic))
            session.commit()
    except Exception as e:
        print(f"Error adding stocks: {e}")


def get_crypto_by_symbols(symbols):
    """Returns {SYMBOL: crypto} for the given tickers. Tickers aren't unique on CoinGecko,
    so for each one the coin with the biggest market cap (lowest id) is taken."""
    found = {}
    if not symbols:
        return found
    try:
        with create_session() as session:
            results = session.query(CryptoRate).filter(CryptoRate.symbol.in_(list(symbols))) \
                .order_by(CryptoRate.id.asc()).all()
            for r in results:
                found.setdefault(r.symbol, {'symbol': r.symbol, 'name': r.coin_id, 'title': r.name,
                                            'price': r.price, 'change_pct': r.change_pct,
                                            'updated_at': r.price_updated_at})
    except Exception as e:
        print(e)
    return found

def get_crypto_by_letter(letter):
    """Returns a list of cryptos starting with a given letter, matching search query, or top-50 (#)."""
    cryptos = []
    try:
        with create_session() as session:
            query = str(letter).strip()
            if query in ('#', 'top', 'TOP', '%23'):
                results = session.query(CryptoRate).order_by(CryptoRate.id.asc()).limit(50).all()
            elif len(query) == 1:
                q_lower = query.lower()
                q_upper = query.upper()
                results = session.query(CryptoRate).filter(
                    or_(
                        CryptoRate.coin_id.startswith(q_lower),
                        CryptoRate.symbol.startswith(q_upper)
                    )
                ).all()
            else:
                pattern = f"%{query}%"
                results = session.query(CryptoRate).filter(
                    or_(
                        CryptoRate.symbol.ilike(pattern),
                        CryptoRate.coin_id.ilike(pattern),
                        CryptoRate.name.ilike(pattern)
                    )
                ).all()

            for r in results:
                cryptos.append({'symbol': r.symbol, 'name': r.coin_id, 'title': r.name,
                                'price': str(r.price) if r.price is not None else "No price data",
                                'change_pct': r.change_pct, 'updated_at': r.price_updated_at})
    except Exception as e:
        print(e)
    return cryptos

def get_all_fiats():
    """Returns all fiat currencies."""
    try:
        with create_session() as session:
            results = session.query(FiatRate).all()
            return [{'code': r.symbol, 'name': r.name, 'price': r.price, 'change_pct': r.change_pct,
                     'rate_date': r.rate_date, 'updated_at': r.updated_at} for r in results]
    except Exception as e:
        print(e)
        return []

def get_all_assets_dict():
    """Reads all assets into dictionaries for fast lookup."""
    assets = {'stocks': {}, 'crypto': {}, 'fiat': {}}
    try:
        with create_session() as session:
            for r in session.query(StockRate).all():
                assets['stocks'][r.ticker] = (r.name, str(r.price) if r.price is not None else "No price data")
            for r in session.query(CryptoRate).all():
                assets['crypto'][r.symbol] = (r.coin_id, str(r.price) if r.price is not None else "No price data")
            for r in session.query(FiatRate).all():
                assets['fiat'][r.symbol] = (r.name, str(r.price) if r.price is not None else "No price data")
    except Exception as e:
        print(e)
    return assets
