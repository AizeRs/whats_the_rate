import sqlalchemy
from .db_session import SqlAlchemyBase
import json


from sqlalchemy.orm.attributes import flag_modified

class Portfolio(SqlAlchemyBase):
    """Represents a user's portfolio in the database."""
    __tablename__ = 'portfolios'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    contains = sqlalchemy.Column(sqlalchemy.JSON,
                                 default={'stocks': {}, 'crypto': {}, 'fiat': {}}
                                 )
    isprivate = sqlalchemy.Column(sqlalchemy.Boolean)

    def get_dict(self):
        """Returns the portfolio contents as a dictionary."""
        if isinstance(self.contains, str):
            return json.loads(self.contains)
        return self.contains if self.contains else {'stocks': {}, 'crypto': {}, 'fiat': {}}

    def set_in_dict(self, ticker_type, ticker, number):
        """Updates the quantity of a specific asset in the portfolio."""
        contains = self.get_dict()
        if ticker not in contains['stocks'].keys() and ticker_type == 'stocks' and len(contains['stocks']) >= 5:
            return 'Too Many Stocks Error'

        if number == 0:
            contains[ticker_type].pop(ticker, None)
        else:
            contains[ticker_type][ticker] = number
        
        self.contains = contains
        flag_modified(self, "contains")
        return True
