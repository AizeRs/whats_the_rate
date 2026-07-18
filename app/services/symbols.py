"""
Defines main currency symbols and provides a function to load their rates.
"""
from app.models.db_session import create_session
from app.models.rates import FiatRate

MAIN_SYMBOLS = {
    'USD': ('$', 1.0), 
    'EUR': ('€', 0), 
    'GBP': ('£', 0), 
    'JPY': ('¥', 0), 
    'CHF': ('₣', 0),
    'BTC': ('₿', 0)
}

def load_main_symbols():
    """Loads fiat rates from the database into MAIN_SYMBOLS."""
    try:
        session = create_session()
        for symbol in MAIN_SYMBOLS:
            fiat = session.query(FiatRate).filter(FiatRate.symbol == symbol).first()
            if fiat and fiat.price:
                MAIN_SYMBOLS[symbol] = (MAIN_SYMBOLS[symbol][0], fiat.price)
    except Exception as e:
        print(f"Error loading main symbols: {e}")
