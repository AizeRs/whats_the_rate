from constants import *
import requests
import csv
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.foreignexchange import ForeignExchange


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


# GET LIST OF CURRENCIES (NOT CRYPTO)
def list_of_currencies():
    data = requests.get(f'https://free.currconv.com/api/v7/currencies?apiKey={CURRONCV_APIKEY}').json()['results']
    currencies = {}
    for key in data.keys():
        currencies[data[key]['id']] = data[key]['currencyName']
    return currencies


# UPDATE LIST OF TICKERS FILE
def update_tickers_file():
    CSV_URL = f'https://www.alphavantage.co/query?function=LISTING_STATUS&apikey={ALPHAVANTAGE_APIKEY}'
    with requests.Session() as s:
        download = s.get(CSV_URL)
        decoded_content = download.content.decode('utf-8')
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)
    lines = []
    old_data = {}
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
    with open('list_of_tickers.txt', 'w') as file_out:
        file_out.writelines(lines)


# SAVE PRICE FOR A TICKER IN LIST FILE
def save_ticker_price(ticker, price):
    lines = []
    with open('list_of_tickers.txt', 'r') as file_in:
        for line in file_in.read().split('\n'):
            if line.split(',')[0] == ticker:
                line = f'{line.split(",")[0]},{line.split(",")[1]},{price}'
            lines.append(f'{line}\n')
    with open('list_of_tickers.txt', 'w') as file_out:
        file_out.writelines(lines)