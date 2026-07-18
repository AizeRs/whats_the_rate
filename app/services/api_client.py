from app.constants import FINNHUB_APIKEY
import requests

def ticker_price(ticker):
    """Fetches the current price and full quote for a given stock ticker."""
    try:
        response = requests.get(f'https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_APIKEY}').json()
        if 'c' in response and response['c'] != 0:
            return response['c'], response
        return None
    except Exception as e:
        print(f"Error fetching ticker price for {ticker}: {e}")
        return None

def fetch_crypto_data():
    """Fetches top crypto data from CoinGecko."""
    lines = []
    for page in (1, 2):
        response = requests.get(
            f'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={page}'
        ).json()
        if isinstance(response, dict) and 'error' in response:
            return False, []
        for elem in response:
            if elem.get("symbol") and elem.get("id") and elem.get("current_price"):
                lines.append(
                    f'{elem["symbol"].upper()},{elem["id"].lower()},{elem["current_price"]}\n')
    return True, lines

def fetch_fiat_data():
    """Fetches fiat data from Frankfurter."""
    names = requests.get('https://api.frankfurter.app/currencies').json()
    prices_resp = requests.get('https://api.frankfurter.app/latest?from=USD').json()
    prices = prices_resp.get('rates', {})
    prices['USD'] = 1.0  # Base currency
    if not (names and prices):
        return False, {}, {}
    return True, names, prices

def fetch_tickers_data():
    """Fetches list of all US tickers from Finnhub."""
    api_url = f'https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_APIKEY}'
    response = requests.get(api_url).json()
    my_list = [[item.get('symbol', ''), item.get('description', '').replace(',', '')] for item in response if item.get('symbol')]
    return my_list
