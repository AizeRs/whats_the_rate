import os
from .api_client import fetch_crypto_data, fetch_fiat_data, fetch_tickers_data

def update_crypto_file():
    success, lines = fetch_crypto_data()
    if not success:
        return False
    try:
        with open('data/list_of_cryptocurrencies.txt', 'w', encoding='utf-8') as file_out:
            file_out.writelines(lines)
        return True
    except Exception as e:
        print(f"Error writing crypto file: {e}")
        return False

def update_currencies_file(main_symbols_dict):
    success, names, prices = fetch_fiat_data()
    if not success:
        return False
    try:
        with open('data/list_of_fiat.txt', 'w', encoding='utf-8') as file:
            for currency in names.keys():
                if currency in prices.keys():
                    rate = 1 / float(prices[currency])
                    file.write(f'{currency},{names[currency]},{rate}\n')
                    if currency in main_symbols_dict:
                        main_symbols_dict[currency] = (main_symbols_dict[currency][0], rate)
        return True
    except Exception as e:
        print(f"Error writing currencies file: {e}")
        return False

def update_tickers_file():
    try:
        my_list = fetch_tickers_data()
    except Exception:
        return False
    
    lines = []
    old_data = {}
    try:
        with open('data/list_of_tickers.txt', 'r', encoding='utf-8') as file_in:
            for row in file_in.read().split('\n'):
                if row:
                    parts = row.split(',')
                    old_data[parts[0]] = parts[-1]
            for row in my_list:
                lines.append(
                    f'{row[0]},{row[1]},{old_data[row[0]] if row[0] in old_data else "No price data"}\n')
    except FileNotFoundError:
        for row in my_list:
            lines.append(
                f'{row[0]},{row[1]},No price data\n')
    
    if not lines:
        return False
    
    try:
        with open('data/list_of_tickers.txt', 'w', encoding='utf-8') as file_out:
            file_out.writelines(lines)
        return True
    except Exception as e:
        print(f"Error writing tickers file: {e}")
        return False

def save_ticker_price(ticker, price):
    try:
        lines = []
        with open('data/list_of_tickers.txt', 'r', encoding='utf-8') as file_in:
            for line in file_in.read().split('\n'):
                if not line:
                    continue
                parts = line.split(',')
                if parts[0] == ticker:
                    line = f'{parts[0]},{parts[1]},{price}'
                lines.append(f'{line}\n')
        with open('data/list_of_tickers.txt', 'w', encoding='utf-8') as file_out:
            file_out.writelines(lines)
        return True
    except Exception as e:
        print(f"Error saving ticker price: {e}")
        return False

def get_stocks_by_letter(letter):
    """Returns a list of stocks starting with a given letter."""
    stocks = []
    try:
        with open('data/list_of_tickers.txt', 'r', encoding='utf-8') as file:
            content = file.read()
            for line in content.split('\n')[1:]:
                if not line or not line.startswith(letter.upper()):
                    continue
                ticker, stock, price = line.split(',')
                stocks.append({'ticker': ticker, 'stock': stock, 'price': price})
    except FileNotFoundError:
        pass
    return stocks

def get_crypto_by_letter(letter):
    """Returns a list of cryptos starting with a given letter."""
    cryptos = []
    try:
        with open('data/list_of_cryptocurrencies.txt', 'r', encoding='utf-8') as file:
            content = file.read()
            flag = letter.isupper()
            for line in content.split('\n'):
                if not line:
                    continue
                symbol, name, price = line.split(',')
                if not ((line.startswith(letter) and flag) or (name.startswith(letter) and not flag)):
                    continue
                cryptos.append({'symbol': symbol, 'name': name, 'price': price})
    except FileNotFoundError:
        pass
    return cryptos

def get_fiat_by_letter(letter, main_symbols_keys=None):
    """Returns a list of fiats matching a given filter."""
    fiats = []
    try:
        with open('data/list_of_fiat.txt', 'r', encoding='utf-8') as file:
            content = file.read()
            for line in content.split('\n'):
                if not line or line.startswith('BTC'):
                    continue
                symbol, name, price = line.split(',')
                
                if letter.isupper() and line.startswith(letter):
                    pass
                elif letter == 'main' and main_symbols_keys and symbol in main_symbols_keys:
                    pass
                elif letter != 'main' and not letter.isupper() and (name.startswith(letter) or letter == 'all'):
                    pass
                else:
                    continue
                
                fiats.append({'symbol': symbol, 'name': name, 'price': price})
    except FileNotFoundError:
        pass
    return fiats

def get_all_assets_dict():
    """Reads all assets into dictionaries for fast lookup."""
    assets = {'stocks': {}, 'crypto': {}, 'fiat': {}}
    
    try:
        with open('data/list_of_tickers.txt', encoding='utf-8') as f:
            for line in f.read().split('\n'):
                if line:
                    parts = line.split(',')
                    assets['stocks'][parts[0]] = (parts[1], parts[2])  # Store tuple of (name, price)
    except FileNotFoundError:
        pass

    try:
        with open('data/list_of_cryptocurrencies.txt', encoding='utf-8') as f:
            for line in f.read().split('\n'):
                if line:
                    parts = line.split(',')
                    assets['crypto'][parts[0]] = (parts[1], parts[2])
    except FileNotFoundError:
        pass

    try:
        with open('data/list_of_fiat.txt', encoding='utf-8') as f:
            for line in f.read().split('\n'):
                if line:
                    parts = line.split(',')
                    assets['fiat'][parts[0]] = (parts[1], parts[2])
    except FileNotFoundError:
        pass
    
    return assets
