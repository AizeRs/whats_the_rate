from datetime import date, timedelta
from app.constants import FINNHUB_APIKEY
import requests

FRANKFURTER_URL = 'https://api.frankfurter.app'

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

def fetch_quote(ticker):
    """Fetches a stock quote from Finnhub.

    Returns (status, quote): status is 'ok', 'limit' (rate limit hit), 'no_data' (unknown ticker
    or no trades) or 'error'; quote is Finnhub's dict ({'c': price, 'dp': change %, ...}) when 'ok'.
    """
    try:
        resp = requests.get('https://finnhub.io/api/v1/quote',
                            params={'symbol': ticker, 'token': FINNHUB_APIKEY}, timeout=10)
    except Exception as e:
        print(f"Error fetching quote for {ticker}: {e}")
        return 'error', None
    if resp.status_code == 429:
        return 'limit', None
    try:
        data = resp.json()
    except ValueError:
        return 'error', None
    if resp.status_code != 200 or not isinstance(data, dict):
        if isinstance(data, dict) and 'limit' in str(data.get('error', '')).lower():
            return 'limit', None
        return 'error', None
    if data.get('c'):
        return 'ok', data
    return 'no_data', None

def _downsample(values, points=42):
    """Thins a long price series (CoinGecko gives 168 hourly points for 7 days) for a small sparkline."""
    if not values or len(values) <= points:
        return values or []
    step = (len(values) - 1) / (points - 1)
    return [values[round(i * step)] for i in range(points)]


def fetch_crypto_data():
    """Fetches the top 250 coins from CoinGecko.

    Returns (success, coins): each coin is a dict with symbol, coin_id, name, price, change_pct (24 h),
    change_7d_pct, market_cap (USD) and sparkline (7 days of USD prices, thinned).
    """
    coins = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    try:
        url = ('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1'
               '&sparkline=true&price_change_percentage=7d')
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                for elem in data:
                    if isinstance(elem, dict) and elem.get("symbol") and elem.get("id") and elem.get("current_price") is not None:
                        coins.append({
                            'symbol': elem['symbol'].upper(),
                            'coin_id': elem['id'].lower(),
                            'name': (elem.get('name') or '').strip(),
                            'price': elem['current_price'],
                            'change_pct': elem.get('price_change_percentage_24h'),
                            'change_7d_pct': elem.get('price_change_percentage_7d_in_currency'),
                            'market_cap': elem.get('market_cap'),
                            'sparkline': _downsample((elem.get('sparkline_in_7d') or {}).get('price') or []),
                        })
                if coins:
                    return True, coins
        print(f"Warning: CoinGecko returned status {resp.status_code}")
        return False, []
    except Exception as e:
        print(f"Error fetching crypto data from CoinGecko: {e}")
        return False, []

def fetch_stock_market_cap(ticker):
    """Market capitalisation of a stock in USD from Finnhub's company profile, or None."""
    try:
        resp = requests.get('https://finnhub.io/api/v1/stock/profile2',
                            params={'symbol': ticker, 'token': FINNHUB_APIKEY}, timeout=10)
        cap = resp.json().get('marketCapitalization') if resp.status_code == 200 else None
        return cap * 1_000_000 if cap else None  # Finnhub gives millions
    except Exception as e:
        print(f"Error fetching profile for {ticker}: {e}")
        return None


def fetch_fiat_history(days=7):
    """ECB fixings of all currencies for the last days: {date: {CODE: units per 1 USD}} or {}."""
    try:
        start = (date.today() - timedelta(days=days)).isoformat()
        data = requests.get(f'{FRANKFURTER_URL}/{start}..', params={'from': 'USD'}, timeout=10).json()
        return {date.fromisoformat(d): rates for d, rates in data.get('rates', {}).items()}
    except Exception as e:
        print(f"Error fetching fiat history: {e}")
        return {}


def fetch_fiat_data():
    """Fetches currency names and the two latest ECB fixings (units per 1 USD) from Frankfurter.

    Returns (success, names, rates, previous_rates, rate_date).
    """
    try:
        names = requests.get(f'{FRANKFURTER_URL}/currencies', timeout=10).json()
        latest = requests.get(f'{FRANKFURTER_URL}/latest', params={'from': 'USD'}, timeout=10).json()
        rate_date = date.fromisoformat(latest['date'])
        # For a weekend/holiday Frankfurter returns the closest earlier fixing, i.e. the previous one
        day_before = (rate_date - timedelta(days=1)).isoformat()
        previous = requests.get(f'{FRANKFURTER_URL}/{day_before}', params={'from': 'USD'}, timeout=10).json()
    except Exception as e:
        print(f"Error fetching fiat data from Frankfurter: {e}")
        return False, {}, {}, {}, None
    rates = latest.get('rates', {})
    previous_rates = previous.get('rates', {})
    rates['USD'] = previous_rates['USD'] = 1.0  # Base currency
    if not (names and rates):
        return False, {}, {}, {}, None
    return True, names, rates, previous_rates, rate_date

def fetch_tickers_data():
    """Fetches list of all US tickers from Finnhub."""
    api_url = f'https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_APIKEY}'
    response = requests.get(api_url).json()
    my_list = [[item.get('symbol', ''), item.get('description', '').replace(',', ''),
                item.get('type') or None, item.get('mic') or None]
               for item in response if item.get('symbol')]
    return my_list
