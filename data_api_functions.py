from constants import *
import requests
import csv
from main import MAIN_SYMBOLS


# GET TICKER PRICE
def ticker_price(ticker):
    try:
        response = requests.get(f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_APIKEY}').json()
        if 'c' in response and response['c'] != 0:
            return response['c'], response
        return None
    except Exception:
        return None


# UPDATE CRYPTOCURRENCIES FILE
def update_crypto_file():
    try:
        lines = []
        for page in (1, 2):
            response = requests.get(
                f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}'
            ).json()
            if isinstance(response, dict) and 'error' in response:
                return False
            for elem in response:
                if elem.get("symbol") and elem.get("id") and elem.get("current_price"):
                    lines.append(
                        f'{elem["symbol"].upper()},{elem["id"].lower()},{elem["current_price"]}\n')
        with open('list_of_cryptocurrencies.txt', 'w', encoding='utf-8') as file_out:
            file_out.writelines(lines)
        return True
    except Exception as e:
        print(e)
        return False


# UPDATE FILE WITH FIAT CURRENCIES
def update_currencies_file():
    try:
        names = requests.get('https://api.frankfurter.app/currencies').json()
        prices_resp = requests.get('https://api.frankfurter.app/latest?from=USD').json()
        prices = prices_resp.get('rates', {})
        prices['USD'] = 1.0  # Base currency
        if not (names and prices):
            return False
        with open('list_of_fiat.txt', 'w', encoding='utf-8') as file:
            for currency in names.keys():
                if currency in prices.keys():
                    rate = 1 / float(prices[currency])
                    file.write(f'{currency},{names[currency]},{rate}\n')
                    if currency in MAIN_SYMBOLS.keys():
                        MAIN_SYMBOLS[currency] = (MAIN_SYMBOLS[currency][0], rate)
        return True
    except Exception as e:
        print(e)
        return False


# UPDATE LIST OF TICKERS FILE
def update_tickers_file():
    try:
        api_url = f'https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_APIKEY}'
        response = requests.get(api_url).json()
        my_list = [[item.get('symbol', ''), item.get('description', '').replace(',', '')] for item in response if item.get('symbol')]
        lines = []
        old_data = {}
    except Exception as e:
        return False
    try:
        with open('list_of_tickers.txt', 'r', encoding='utf-8') as file_in:
            if file_in:
                for row in file_in.read().split('\n'):
                    if row:
                        parts = row.split(',')
                        old_data[parts[0]] = parts[-1]
                for row in my_list:
                    lines.append(
                        f'{row[0]},{row[1]},{old_data[row[0]] if row[0] in old_data.keys() else "No price data"}\n')
    except FileNotFoundError:
        for row in my_list:
            lines.append(
                f'{row[0]},{row[1]},No price data\n')
    if not lines:
        return False
    with open('list_of_tickers.txt', 'w', encoding='utf-8') as file_out:
        file_out.writelines(lines)
    return True


# SAVE PRICE FOR A TICKER IN LIST FILE
def save_ticker_price(ticker, price):
    try:
        lines = []
        with open('list_of_tickers.txt', 'r') as file_in:
            for line in file_in.read().split('\n'):
                if line.split(',')[0] == ticker:
                    line = f'{line.split(",")[0]},{line.split(",")[1]},{price}'
                lines.append(f'{line}\n')
        with open('list_of_tickers.txt', 'w') as file_out:
            file_out.writelines(lines)
        return True
    except Exception as e:
        print(e)
        return False
