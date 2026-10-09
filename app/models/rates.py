import sqlalchemy
from .db_session import SqlAlchemyBase

class StockRate(SqlAlchemyBase):
    """Stores the current rate for a stock."""
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
    """Stores the current rate for a cryptocurrency."""
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
    price_updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)  # When the quotes were last loaded

class FiatRate(SqlAlchemyBase):
    """Stores the current rate for a fiat currency."""
    __tablename__ = 'fiat_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    symbol = sqlalchemy.Column(sqlalchemy.String, unique=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # USD per 1 unit
    change_pct = sqlalchemy.Column(sqlalchemy.Float, nullable=True)  # Change vs the previous ECB fixing, % (in USD)
    rate_date = sqlalchemy.Column(sqlalchemy.Date, nullable=True)  # Date of the ECB fixing
    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)  # When we loaded the rates
