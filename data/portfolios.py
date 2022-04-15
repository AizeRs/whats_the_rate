import sqlalchemy
from .db_session import SqlAlchemyBase
from pickle import dumps, loads


class Portfolio(SqlAlchemyBase):
    __tablename__ = 'portfolios'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    contains = sqlalchemy.Column(sqlalchemy.PickleType,
                                 default=dumps({'stocks': {}, 'crypto': {}, 'fiat': {}})
                                 )
    isprivate = sqlalchemy.Column(sqlalchemy.Boolean)
    last_price = sqlalchemy.Column(sqlalchemy.Integer, default=1)

    def get_dict(self):
        return loads(self.contains)

    def set_in_dict(self, ticker_type, ticker, number):
        contains = loads(self.contains)
        if ticker not in self.get_dict()['stocks'].keys() and ticker_type == 'stocks' and len(contains['stocks']) >= 5:
            return 'Too Many Stocks Error'

        if number == 0:
            contains[ticker_type].pop(ticker, None)
        else:
            contains[ticker_type][ticker] = number
        self.contains = dumps(contains)
