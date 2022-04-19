from flask import Flask, render_template, redirect, session, url_for, request, Blueprint, jsonify

from data import db_session
from data.users import User
from data.portfolios import Portfolio
from main import MAIN_SYMBOLS
import data_api_functions

blueprint = Blueprint('api', __name__)


@blueprint.route('/api/help')
def api_help():
    return '''Для получения данных о стоимости вашего портфеля отправьте запрос на "/api/portfolio_price". \n \
           Параметры запроса: apikey="апи ключ, полученный в личном кабинете"&base_currency="Желаемая валюта в  \
           которой будет рассчитана цена портфеля. По умолчанию берётся валюта, выбранная в профиле"\n \
           Для обновления данных о стоимости вашего портфеля отправьте запрос на "/api/reload_portfolio" \n \
           Параметры запроса: apikey="апи ключ, полученный в личном кабинете" \n'''


@blueprint.route('/api/portfolio_price')
def portfolio_price():
    apikey = request.args.get('apikey', default=None, type=int)
    base_currency = request.args.get('base_currency', default='user', type=str)
    if apikey is None:
        return jsonify({'Error': 'No apikey'})
    if base_currency not in MAIN_SYMBOLS.keys() and base_currency != 'user':
        return jsonify({'Error': f'base_currency must be one of: {MAIN_SYMBOLS.keys()}'})
    if base_currency != 'user':
        pref_symbol = MAIN_SYMBOLS[base_currency]
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.apikey == apikey).all()
    if not user:
        return jsonify({'Error': 'Invalid apikey'})
    user = user[0]
    if base_currency == 'user':
        pref_symbol = MAIN_SYMBOLS[user.main_currency]
    if not user.portfolio_id:
        return jsonify({'Error': 'User has no portfolio'})
    portfolio = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).all()
    if not portfolio:
        return jsonify({'Internal Error': 'Portfolio does not exist'})

    portfolio = portfolio[0]
    data = portfolio.get_dict()
    response = 0.0
    with open('list_of_tickers.txt', encoding='utf-8') as stocks_file, \
            open('list_of_cryptocurrencies.txt', encoding='utf-8') as crypto_file, \
            open('list_of_fiat.txt', encoding='utf-8') as fiat_file:

        for line in stocks_file.read().split('\n'):
            if not line:
                continue
            for current_stock in data['stocks'].keys():
                tck, name, price = line.split(',')
                if tck == current_stock:
                    try:
                        response += float(price) * data['stocks'][current_stock]
                    except ValueError:
                        continue
        for line in crypto_file.read().split('\n'):
            if not line:
                continue
            for current_crypto in data['crypto'].keys():
                tck, name, price = line.split(',')
                if tck == current_crypto:
                    try:
                        response += float(price) * data['crypto'][current_crypto]
                    except ValueError:
                        continue
        for line in fiat_file.read().split('\n'):
            if not line:
                continue
            for current_fiat in data['fiat'].keys():
                tck, name, price = line.split(',')
                if tck == current_fiat:
                    try:
                        response += float(price) * data['fiat'][current_fiat]
                    except ValueError:
                        continue
    float_response = response / pref_symbol[1]
    str_response = str(float_response) + pref_symbol[0]

    return jsonify({'price': str_response, 'price_float': float_response})


@blueprint.route('/api/reload_portfolio')
def reload_portfolio():
    apikey = request.args.get('apikey', default=None, type=int)

    if apikey is None:
        return jsonify({'Error': 'No apikey'})
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.apikey == apikey).all()
    if not user:
        return jsonify({'Error': 'Invalid apikey'})
    user = user[0]

    if not user.portfolio_id:
        return jsonify({'Error': 'User has no portfolio'})
    portfolio = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).all()
    if not portfolio:
        return jsonify({'Internal Error': 'Portfolio does not exist'})
    portfolio = portfolio[0]

    data = portfolio.get_dict()
    for ticker in data['stocks'].keys():
        price = data_api_functions.ticker_price(ticker)[0]
        if price:
            data_api_functions.save_ticker_price(ticker, price)
        else:
            return jsonify({'Error': 'Stocks API limit exceeded'})
    if data['crypto']:
        data_api_functions.update_crypto_file()
    if data['fiat']:
        data_api_functions.update_currencies_file()
    return 'Success'
