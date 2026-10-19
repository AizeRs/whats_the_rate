import sqlalchemy
from .db_session import SqlAlchemyBase

class StockRate(SqlAlchemyBase):
    """Stores the current rate for a stock"""
    __tablename__ = 'stock_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    ticker = sqlalchemy.Column(sqlalchemy.String, unique=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    type = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Finnhub security type: "Common Stock", "ETP", "ADR"...
    mic = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # Exchange code: XNAS, XNYS, ..., OOTC = over-the-counter
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    change_pct = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # Daily change, % (Finnhub "dp")
    market_cap = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # USD, Finnhub profile (home page stocks only)
    price_updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)  # When WE saved the price

class CryptoRate(SqlAlchemyBase):
    """Stores the current rate for a cryptocurrency"""
    __tablename__ = 'crypto_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    symbol = sqlalchemy.Column(sqlalchemy.String, index=True)
    coin_id = sqlalchemy.Column(sqlalchemy.String, unique=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)  
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    change_pct = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # Change over 24 h, % (CoinGecko)
    change_7d_pct = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # Change over 7 days, %
    market_cap = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # USD
    sparkline = sqlalchemy.Column(sqlalchemy.Text, nullable=True)  # JSON list: 7 days of USD prices, thinned
    image = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # CoinGecko logo URL ('large', 250 px)
    price_updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)  # When the quotes were last loaded

class FiatRate(SqlAlchemyBase):
    """Stores the current rate for a fiat currency"""
    __tablename__ = 'fiat_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    symbol = sqlalchemy.Column(sqlalchemy.String, unique=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # USD per 1 unit
    change_pct = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # Change vs the previous ECB fixing, % (in USD)
    rate_date = sqlalchemy.Column(sqlalchemy.Date, nullable=True)  # Date of the ECB fixing
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)  # When we loaded the rates


class FiatHistory(SqlAlchemyBase):
    """ECB fixings of the last days: the 7-day change and sparkline of currencies on the home page"""
    __tablename__ = 'fiat_history'
    __table_args__ = (sqlalchemy.UniqueConstraint('rate_date', 'symbol'),)

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    rate_date = sqlalchemy.Column(sqlalchemy.Date, nullable=False, index=True)  # Date of the ECB fixing
    symbol = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    per_usd = sqlalchemy.Column(sqlalchemy.Float, nullable=False)  # Units of the currency per 1 USD


class DataUpdate(SqlAlchemyBase):
    """When a whole data set was last loaded, for sets without a timestamp of their own (e.g. the ticker list)"""
    __tablename__ = 'data_updates'

    source = sqlalchemy.Column(sqlalchemy.String, primary_key=True)  # 'tickers'
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
