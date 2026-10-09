import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import db_session, __all_models  # noqa: F401
from app.models.portfolios import Portfolio
from app.models.rates import CryptoRate, FiatRate


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh SQLite file per test with a few known currencies."""
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}')
    db_session.SqlAlchemyBase.metadata.create_all(engine)
    monkeypatch.setattr(db_session, '__factory', sessionmaker(bind=engine))
    with db_session.create_session() as session:
        session.add_all([
            FiatRate(symbol='USD', name='US Dollar'),
            FiatRate(symbol='EUR', name='Euro'),
            CryptoRate(symbol='ETH', coin_id='ethereum'),
        ])
        session.commit()
    yield
    engine.dispose()


@pytest.fixture
def portfolio(db):
    with db_session.create_session() as session:
        pf = Portfolio(contains={'stocks': {}, 'crypto': {'ETH': 2}, 'fiat': {'USD': 5000}}, isprivate=False)
        session.add(pf)
        session.commit()
        return pf.id
