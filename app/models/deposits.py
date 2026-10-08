import sqlalchemy
from datetime import datetime
from .db_session import SqlAlchemyBase


class Deposit(SqlAlchemyBase):
    """A bank deposit or crypto staking in a portfolio. The balance is calculated from the events."""
    __tablename__ = 'deposits'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    portfolio_id = sqlalchemy.Column(sqlalchemy.Integer, index=True)
    kind = sqlalchemy.Column(sqlalchemy.String)  # 'fiat' | 'crypto', also the portfolio section
    asset = sqlalchemy.Column(sqlalchemy.String)
    title = sqlalchemy.Column(sqlalchemy.String)
    amount = sqlalchemy.Column(sqlalchemy.Float)
    rate = sqlalchemy.Column(sqlalchemy.Float)  # Current rate, % as entered
    rate_type = sqlalchemy.Column(sqlalchemy.String)  # 'nominal' | 'apy'
    frequency = sqlalchemy.Column(sqlalchemy.String)  # 'daily' | 'monthly' | 'quarterly' | 'yearly' | 'end'
    capitalize = sqlalchemy.Column(sqlalchemy.Boolean)
    base = sqlalchemy.Column(sqlalchemy.String, default='daily')  # 'daily' | 'min' balance
    opened_at = sqlalchemy.Column(sqlalchemy.Date)
    ends_at = sqlalchemy.Column(sqlalchemy.Date, nullable=True)
    last_settled_at = sqlalchemy.Column(sqlalchemy.Date)  # Payouts up to this day are in the portfolio
    closed_at = sqlalchemy.Column(sqlalchemy.Date, nullable=True)
    close_reason = sqlalchemy.Column(sqlalchemy.String, nullable=True)  # 'matured' | 'early'
    returned = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.now)


class DepositEvent(SqlAlchemyBase):
    __tablename__ = 'deposit_events'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    deposit_id = sqlalchemy.Column(sqlalchemy.Integer, index=True)
    kind = sqlalchemy.Column(sqlalchemy.String)  # 'open' | 'topup' | 'withdraw' | 'rate' | 'payout' | 'close'
    day = sqlalchemy.Column(sqlalchemy.Date)
    amount = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    rate = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    rate_type = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    linked = sqlalchemy.Column(sqlalchemy.Boolean, default=False)  # Money taken from / moved to the portfolio
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.now)


class DepositNotice(SqlAlchemyBase):
    """Shown on the deposit card until the owner presses «Понятно»."""
    __tablename__ = 'deposit_notices'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    portfolio_id = sqlalchemy.Column(sqlalchemy.Integer, index=True)
    deposit_id = sqlalchemy.Column(sqlalchemy.Integer, index=True)
    kind = sqlalchemy.Column(sqlalchemy.String)  # 'payout' | 'matured'
    section = sqlalchemy.Column(sqlalchemy.String)
    asset = sqlalchemy.Column(sqlalchemy.String)
    amount = sqlalchemy.Column(sqlalchemy.Float)
    interest = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    principal = sqlalchemy.Column(sqlalchemy.Float, nullable=True)
    period_from = sqlalchemy.Column(sqlalchemy.Date, nullable=True)
    period_to = sqlalchemy.Column(sqlalchemy.Date, nullable=True)
    payouts = sqlalchemy.Column(sqlalchemy.Integer, default=1)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.now)
    acknowledged_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
