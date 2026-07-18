from flask import request, Blueprint, jsonify
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import update_crypto_db, update_currencies_db, save_ticker_price, get_all_assets_dict
from app.services.api_client import ticker_price

from app.utils import format_price, get_portfolio_details

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/help')
def api_help():
    return '''Для получения данных о стоимости вашего портфеля отправьте запрос на "/api/portfolio_price". \n \
           Параметры запроса: apikey="апи ключ, полученный в личном кабинете"&base_currency="Желаемая валюта в  \
           которой будет рассчитана цена портфеля. По умолчанию берётся валюта, выбранная в профиле"\n \
           Для обновления данных о стоимости вашего портфеля отправьте запрос на "/api/reload_portfolio" \n \
           Параметры запроса: apikey="апи ключ, полученный в личном кабинете" \n'''


@api_bp.route('/api/portfolio_price')
def portfolio_price():
    apikey = request.args.get('apikey', default=None, type=str)
    base_currency = request.args.get('base_currency', default='user', type=str)
    
    if apikey is None:
        return jsonify({'Error': 'No apikey'}), 401
        
    if base_currency not in MAIN_SYMBOLS and base_currency != 'user':
        return jsonify({'Error': f'base_currency must be one of: {list(MAIN_SYMBOLS.keys())}'}), 400
        
    if base_currency != 'user':
        pref_symbol = MAIN_SYMBOLS[base_currency]
        
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.apikey == apikey).first()
        if not user:
            return jsonify({'Error': 'Invalid apikey'}), 401
            
        if base_currency == 'user':
            pref_symbol = MAIN_SYMBOLS[user.main_currency]
            
        if not user.portfolio_id:
            return jsonify({'Error': 'User has no portfolio'}), 404
            
        portfolio = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).first()
        if not portfolio:
            return jsonify({'Internal Error': 'Portfolio does not exist'}), 500

        data = portfolio.get_dict()

    all_assets = get_all_assets_dict()
    details = get_portfolio_details(data, all_assets, pref_symbol)
    
    return jsonify({'price': details['sums']['total_str'], 'price_float': details['sums']['total_val']})


@api_bp.route('/api/reload_portfolio')
def reload_portfolio():
    apikey = request.args.get('apikey', default=None, type=str)

    if apikey is None:
        return jsonify({'Error': 'No apikey'}), 401
        
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.apikey == apikey).first()
        if not user:
            return jsonify({'Error': 'Invalid apikey'}), 401

        if not user.portfolio_id:
            return jsonify({'Error': 'User has no portfolio'}), 404
            
        portfolio = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).first()
        if not portfolio:
            return jsonify({'Internal Error': 'Portfolio does not exist'}), 500
            
        data = portfolio.get_dict()

    for ticker in data['stocks'].keys():
        price_data = ticker_price(ticker)
        if price_data and price_data[0]:
            save_ticker_price(ticker, price_data[0])
        else:
            return jsonify({'Error': 'Stocks API limit exceeded'})
            
    if data['crypto']:
        update_crypto_db()
    if data['fiat']:
        update_currencies_db(MAIN_SYMBOLS)
        
    return 'Success'
