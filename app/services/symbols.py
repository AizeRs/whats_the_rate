import os

MAIN_SYMBOLS = {
    'USD': ('$', 1.0), 
    'EUR': ('€', 0), 
    'GBP': ('£', 0), 
    'JPY': ('¥', 0), 
    'CHF': ('₣', 0),
    'BTC': ('₿', 0)
}

def load_main_symbols():
    """Loads fiat rates from list_of_fiat.txt into MAIN_SYMBOLS."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        fiat_path = os.path.join(base_dir, 'data/list_of_fiat.txt')
        with open(fiat_path, 'r', encoding='utf-8') as file:
            fiats = file.read()
            for line in fiats.split('\n'):
                if not line:
                    continue
                symbol, name, cur_price = line.split(',')
                if symbol in MAIN_SYMBOLS:
                    MAIN_SYMBOLS[symbol] = (MAIN_SYMBOLS[symbol][0], float(cur_price))
    except FileNotFoundError:
        pass

# Load initial values on module import.
load_main_symbols()
