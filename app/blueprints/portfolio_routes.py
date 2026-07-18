from flask import Blueprint, render_template, request, url_for
from flask_login import current_user
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import update_crypto_db, update_currencies_db, save_ticker_price, get_all_assets_dict
from app.services.api_client import ticker_price
from app.utils import format_price, get_portfolio_details

portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route('/portfolios/<username>', methods=['GET', 'POST'])
def portfolios_username(username):
    """Renders the portfolio page for a specific user, handling asset updates and data reloads."""
    param = {'username': username, 'stocks': [], 'cryptos': [], 'fiats': []}
    
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.username == username).first()
        if not user:
            return render_template('portfolios.html', **param)

        pf = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id).first()
        if not pf:
            param['not_found'] = True
            return render_template('portfolios.html', **param)

        if pf.isprivate and (not current_user.is_authenticated or current_user.id != user.id):
            param['no_access'] = True
            return render_template('portfolios.html', **param)

        if current_user.is_authenticated:
            pref_symbol = MAIN_SYMBOLS[current_user.main_currency]
            if current_user.id == user.id:
                param['is_owner'] = True
        else:
            pref_symbol = MAIN_SYMBOLS['USD']

        data = pf.get_dict()

        if request.method == 'POST':
            if request.form.get('reload'):
                for ticker in data['stocks'].keys():
                    price = ticker_price(ticker)
                    if price and price[0]:
                        param['success_btn'] = 'reload'
                        save_ticker_price(ticker, price[0])
                    else:
                        param['danger_btn'] = 'reload'
                if data['crypto']:
                    update_crypto_db()
                if data['fiat']:
                    update_currencies_db(MAIN_SYMBOLS)

        # Fetch current asset prices from the database
        assets_cache = get_all_assets_dict()

        # Handle manual updates to asset quantities
        if request.method == 'POST' and not request.form.get('reload'):
            def handle_asset_update(dict_key):
                for symbol in data.get(dict_key, {}).keys():
                    if request.form.get(f"{dict_key}_{symbol}_btn"):
                        new_number_str = request.form.get(f"{dict_key}_{symbol}")
                        try:
                            new_number = float(new_number_str[1:]) if new_number_str.startswith('x') else float(new_number_str)
                        except (ValueError, TypeError):
                            name = assets_cache.get(dict_key, {}).get(symbol, [symbol])[0]
                            param['danger_btn'] = name
                            return True
                            
                        pf.set_in_dict(dict_key, symbol, new_number)
                        name = assets_cache.get(dict_key, {}).get(symbol, [symbol])[0]
                        param['success_btn'] = name
                        db_sess.commit()
                        return True
                return False

            if not handle_asset_update('stocks'):
                if not handle_asset_update('crypto'):
                    handle_asset_update('fiat')
                    
            # Reload dictionary after changes
            data = pf.get_dict()

        details = get_portfolio_details(data, assets_cache, pref_symbol)
        
        param['stocks'] = details['assets']['stocks']
        param['cryptos'] = details['assets']['crypto']
        param['fiats'] = details['assets']['fiat']
        
        param['stocks_sum'] = details['sums']['stocks_str']
        param['cryptos_sum'] = details['sums']['crypto_str']
        param['fiats_sum'] = details['sums']['fiat_str']
        param['portfolio_sum'] = details['sums']['total_str']

    return render_template('portfolios.html', **param)
