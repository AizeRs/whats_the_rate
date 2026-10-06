import os
from app.models.db_session import create_session
from app.models.rates import StockRate, CryptoRate, FiatRate
from .api_client import fetch_crypto_data, fetch_fiat_data, fetch_tickers_data

def update_crypto_db():
    """Updates the database with the latest cryptocurrency prices."""
    success, data = fetch_crypto_data()
    if not success:
        return False
    try:
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
        for row in my_list:
            ticker_symbol, description = row[0], row[1]
            stock = session.query(StockRate).filter(StockRate.ticker == ticker_symbol).first()
            if not stock:
                stock = StockRate(ticker=ticker_symbol, name=description)
                session.add(stock)
        session.commit()
        return True
    except Exception as e:
        print(f"Error writing tickers to db: {e}")
        return False

def save_ticker_price(ticker, price):
    """Saves a new price for a specific stock ticker."""
    try:
        session = create_session()
        stock = session.query(StockRate).filter(StockRate.ticker == ticker).first()
        if stock:
            stock.price = price
            session.commit()
            return True
        return False
    except Exception as e:
        print(f"Error saving ticker price to db: {e}")
        return False

def get_stocks_by_letter(letter):
    """Returns a list of stocks starting with a given letter."""
    stocks = []
    try:
        session = create_session()
        results = session.query(StockRate).filter(StockRate.ticker.startswith(letter.upper())).all()
        for r in results:
            stocks.append({'ticker': r.ticker, 'stock': r.name, 'price': str(r.price) if r.price is not None else "No price data"})
    except Exception as e:
        print(e)
    return stocks

def get_crypto_by_letter(letter):
    """Returns a list of cryptos starting with a given letter, matching search query, or top-50 (#)."""
    cryptos = []
    try:
        session = create_session()
        query = str(letter).strip()
        if query in ('#', 'top', 'TOP', '%23'):
            results = session.query(CryptoRate).order_by(CryptoRate.id.asc()).limit(50).all()
        elif len(query) == 1:
            from sqlalchemy import or_
            q_lower = query.lower()
            q_upper = query.upper()
            results = session.query(CryptoRate).filter(
                or_(
                    CryptoRate.coin_id.startswith(q_lower),
                    CryptoRate.symbol.startswith(q_upper)
                )
            ).all()
        else:
            from sqlalchemy import or_
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
