"""Background reloads of market data that is shared by the whole site: crypto quotes, fiat rates, the ticker list.

A page with old data asks the server to reload it (static/js/market.js, home.js).
The server reloads only while the data is still old and not more often than once a minute per source.
"""
from datetime import datetime, timedelta
from app.presenters import CRYPTO_AUTO_REFRESH_AFTER, FIAT_AUTO_REFRESH_AFTER, TICKERS_AUTO_REFRESH_AFTER
from app.services.data_service import (
    get_crypto_updated_at, get_fiat_updated_at, get_tickers_updated_at,
    update_crypto_db, update_currencies_db, update_tickers_db
)
from app.services.symbols import MAIN_SYMBOLS

RETRY_AFTER = timedelta(minutes=1)

# source: (when it was last loaded, how long it stays fresh, how to reload it)
_SOURCES = {
    'crypto': (get_crypto_updated_at, CRYPTO_AUTO_REFRESH_AFTER, update_crypto_db),
    'fiat': (get_fiat_updated_at, FIAT_AUTO_REFRESH_AFTER, lambda: update_currencies_db(MAIN_SYMBOLS)),
    'tickers': (get_tickers_updated_at, TICKERS_AUTO_REFRESH_AFTER, update_tickers_db),
}
_last_attempt = {}  # per worker


def is_due(source):
    """True when the data is old and nobody tried to reload it in the last minute."""
    updated_at, max_age, _ = _SOURCES[source]
    loaded = updated_at()
    now = datetime.now()
    last = _last_attempt.get(source)
    return (not loaded or now - loaded > max_age) and not (last and now - last < RETRY_AFTER)


def reload(source):
    """Reloads the data if it's due. True only when fresh data was saved."""
    if not is_due(source):
        return False
    _last_attempt[source] = datetime.now()
    return bool(_SOURCES[source][2]())
