from flask import request, Blueprint, jsonify
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import update_crypto_db, update_currencies_db, save_ticker_price, get_all_assets_dict
from app.services.api_client import ticker_price

from app.utils import format_price

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
    apikey = request.args.get('apikey', default=None, type=int)
    base_currency = request.args.get('base_currency', default='user', type=str)
    
    if apikey is None:
        return jsonify({'Error': 'No apikey'})
        
    if base_currency not in MAIN_SYMBOLS and base_currency != 'user':
        return jsonify({'Error': f'base_currency must be one of: {list(MAIN_SYMBOLS.keys())}'})
        
    if base_currency != 'user':
        pref_symbol = MAIN_SYMBOLS[base_currency]
        
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.apikey == apikey).first()
        if not user:
            return jsonify({'Error': 'Invalid apikey'})
            
        if base_currency == 'user':
            pref_symbol = MAIN_SYMBOLS[user.main_currency]
            
        if not user.portfolio_id:
            return jsonify({'Error': 'User has no portfolio'})
            
        portfolio = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).first()
        if not portfolio:
            return jsonify({'Internal Error': 'Portfolio does not exist'})

        data = portfolio.get_dict()

    response = 0.0
    all_assets = get_all_assets_dict()
    
    for current_stock, count in data['stocks'].items():
        if current_stock in all_assets['stocks']:
            try:
                response += float(all_assets['stocks'][current_stock][1]) * count
            except ValueError:
                pass

    for current_crypto, count in data['crypto'].items():
        if current_crypto in all_assets['crypto']:
            try:
                response += float(all_assets['crypto'][current_crypto][1]) * count
            except ValueError:
                pass
                
    for current_fiat, count in data['fiat'].items():
        if current_fiat in all_assets['fiat']:
            try:
                response += float(all_assets['fiat'][current_fiat][1]) * count
            except ValueError:
                pass

    float_response = response / pref_symbol[1]
    str_response = f"{format_price(float_response)}{pref_symbol[0]}"

    return jsonify({'price': str_response, 'price_float': float_response})


@api_bp.route('/api/reload_portfolio')
def reload_portfolio():
    apikey = request.args.get('apikey', default=None, type=int)

    if apikey is None:
        return jsonify({'Error': 'No apikey'})
        
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.apikey == apikey).first()
        if not user:
            return jsonify({'Error': 'Invalid apikey'})

        if not user.portfolio_id:
            return jsonify({'Error': 'User has no portfolio'})
            
        portfolio = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).first()
        if not portfolio:
            return jsonify({'Internal Error': 'Portfolio does not exist'})
            
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
