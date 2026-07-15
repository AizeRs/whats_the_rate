import sqlalchemy
from .db_session import SqlAlchemyBase

class StockRate(SqlAlchemyBase):
    __tablename__ = 'stock_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    ticker = sqlalchemy.Column(sqlalchemy.String, unique=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)

class CryptoRate(SqlAlchemyBase):
    __tablename__ = 'crypto_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    symbol = sqlalchemy.Column(sqlalchemy.String, index=True)
    coin_id = sqlalchemy.Column(sqlalchemy.String, unique=True)
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)

class FiatRate(SqlAlchemyBase):
    __tablename__ = 'fiat_rates'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    symbol = sqlalchemy.Column(sqlalchemy.String, unique=True, index=True)
    name = sqlalchemy.Column(sqlalchemy.String)
    price = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
