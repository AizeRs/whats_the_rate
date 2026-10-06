import os
from datetime import datetime
from sqlalchemy import or_, func, case
from app.models.db_session import create_session
from app.models.rates import StockRate, CryptoRate, FiatRate
from .api_client import fetch_crypto_data, fetch_fiat_data, fetch_tickers_data

def update_crypto_db():
    """Updates the database with the latest cryptocurrency prices."""
    success, data = fetch_crypto_data()
    if not success:
        return False
    try:
        now = datetime.now()
        with create_session() as session:
            for line in data:
                if not line.strip():
                    continue
                # Name goes last: it may contain commas
                symbol, coin_id, price, name = line.strip().split(',', 3)
                crypto = session.query(CryptoRate).filter(CryptoRate.coin_id == coin_id).first()
                if not crypto:
                    crypto = CryptoRate(symbol=symbol, coin_id=coin_id)
                    session.add(crypto)
                crypto.price = float(price) if price else None
                crypto.name = name or None
                crypto.price_updated_at = now
            session.commit()
        return True
    except Exception as e:
        print(f"Error writing crypto to db: {e}")
        return False

def update_currencies_db(main_symbols_dict):
    """Updates the database with the latest fiat currency prices."""
    success, names, prices = fetch_fiat_data()
    if not success:
        return False
    try:
        session = create_session()
        for currency, name in names.items():
            if currency in prices:
                rate = 1 / float(prices[currency])
                fiat = session.query(FiatRate).filter(FiatRate.symbol == currency).first()
                if not fiat:
                    fiat = FiatRate(symbol=currency, name=name)
                    session.add(fiat)
                fiat.price = rate
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
        session = create_session()
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
        session = create_session()
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
            'change_pct': r.change_pct, 'updated_at': r.price_updated_at}


def get_stocks_by_letter(query, page=1, per_page=50):
    """Returns (stocks, has_next): one page of stocks — listed before OTC, priced first, then by ticker.

    A single character filters by the first letter of the ticker; a longer query matches
    the beginning of the ticker or any part of the company name.
    """
    stocks, has_next = [], False
    try:
        session = create_session()
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
        session = create_session()
        results = session.query(StockRate).filter(StockRate.ticker.in_(list(tickers))) \
            .order_by(StockRate.ticker.asc()).all()
        return [_stock_dict(r) for r in results]
    except Exception as e:
        print(e)
        return []

def get_crypto_updated_at():
    """When the crypto quotes were last loaded (None if never)."""
    try:
        session = create_session()
        return session.query(func.max(CryptoRate.price_updated_at)).scalar()
    except Exception as e:
        print(e)
        return None

def get_crypto_by_letter(letter):
    """Returns a list of cryptos starting with a given letter, matching search query, or top-50 (#)."""
    cryptos = []
    try:
        session = create_session()
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
                            'price': str(r.price) if r.price is not None else "No price data"})
    except Exception as e:
        print(e)
    return cryptos

def get_fiat_by_letter(letter, main_symbols_keys=None):
    """Returns a list of fiats matching a given filter."""
    fiats = []
    try:
        session = create_session()
        query = session.query(FiatRate).filter(FiatRate.symbol != 'BTC')
        
        if letter.isupper():
            query = query.filter(FiatRate.symbol.startswith(letter))
        elif letter == 'main' and main_symbols_keys:
            query = query.filter(FiatRate.symbol.in_(main_symbols_keys))
        elif letter != 'main' and not letter.isupper() and letter != 'all':
            query = query.filter(FiatRate.name.startswith(letter))
            
        results = query.all()
        for r in results:
            fiats.append({'symbol': r.symbol, 'name': r.name, 'price': str(r.price) if r.price is not None else "No price data"})
    except Exception as e:
        print(e)
    return fiats

def get_all_assets_dict():
    """Reads all assets into dictionaries for fast lookup."""
    assets = {'stocks': {}, 'crypto': {}, 'fiat': {}}
    try:
        session = create_session()
        for r in session.query(StockRate).all():
            assets['stocks'][r.ticker] = (r.name, str(r.price) if r.price is not None else "No price data")
        for r in session.query(CryptoRate).all():
            assets['crypto'][r.symbol] = (r.coin_id, str(r.price) if r.price is not None else "No price data")
        for r in session.query(FiatRate).all():
            assets['fiat'][r.symbol] = (r.name, str(r.price) if r.price is not None else "No price data")
    except Exception as e:
        print(e)
    return assets
