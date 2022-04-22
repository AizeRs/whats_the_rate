from constants import *
import requests
import csv
from alpha_vantage.timeseries import TimeSeries
from main import MAIN_SYMBOLS


# GET TICKER PRICE
def ticker_price(ticker):
    try:
        ts = TimeSeries(key=ALPHAVANTAGE_APIKEY)
        data, meta_data = ts.get_intraday(ticker)
        price = data[[*data.keys()][0]]['4. close']
        return price, data
    except ValueError:
        return None


# UPDATE CRYPTOCURRENCIES FILE
def update_crypto_file():
    try:
        lines = []
        response = requests.get(
            f'https://data.messari.io/api/v2/assets?fields=slug,symbol,'
            f'metrics/market_data/price_usd&limit=500&x-messari-api-key={MESSARI_APIKEY}').json()
        if 'error_code' in response['status'].keys():
            return False
        for elem in response['data']:
            if elem["symbol"] and elem["slug"] and elem["metrics"]["market_data"]["price_usd"]:
                lines.append(
                    f'{elem["symbol"].upper()},{elem["slug"].lower()},{elem["metrics"]["market_data"]["price_usd"]}\n')
        with open('list_of_cryptocurrencies.txt', 'w') as file_out:
            file_out.writelines(lines)
        return True
    except Exception as e:
        print(e)
        return False


# UPDATE FILE WITH FIAT CURRENCIES
def update_currencies_file():
    try:
        names = requests.get(f'https://openexchangerates.org/api/currencies.json?app_id={OER_APIKEY}').json()
        prices = requests.get(f'https://openexchangerates.org/api/latest.json?app_id={OER_APIKEY}').json()['rates']
        if not (names and prices):
            return False
        with open('list_of_fiat.txt', 'w', encoding='utf-8') as file:
            for currency in names.keys():
                if currency in prices.keys():
                    file.write(f'{currency},{names[currency]},{1 / float(prices[currency])}\n')
                    if currency in MAIN_SYMBOLS.keys():
                        MAIN_SYMBOLS[currency] = (MAIN_SYMBOLS[currency][0], 1 / float(prices[currency]))
        return True
    except Exception as e:
        print(e)
        return False


# UPDATE LIST OF TICKERS FILE
def update_tickers_file():
    try:
        csv_url = f'https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={ALPHAVANTAGE_APIKEY}'
        with requests.Session() as s:
            download = s.get(csv_url)
            decoded_content = download.content.decode('utf-8')
            cr = csv.reader(decoded_content.splitlines(), delimiter=',')
            my_list = list(cr)
        lines = []
        old_data = {}
    except Exception as e:
        return False
    try:
        with open('list_of_tickers.txt', 'r') as file_in:
            if file_in:
                for row in file_in.read().split('\n'):
                    if row:
                        ticker, _, price = row.split(',')
                        old_data[ticker] = price
                for row in my_list:
                    lines.append(
                        f'{row[0]},{row[1]},{old_data[row[0]] if row[0] in old_data.keys() else "No price data"}\n')
    except FileNotFoundError:
        for row in my_list:
            lines.append(
                f'{row[0]},{row[1]},No price data\n')
    if not lines:
        return False
    with open('list_of_tickers.txt', 'w') as file_out:
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
