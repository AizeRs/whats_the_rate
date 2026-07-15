from flask import Blueprint, render_template, request, url_for
from flask_login import current_user
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import update_crypto_db, update_currencies_db, save_ticker_price, get_all_assets_dict
from app.services.api_client import ticker_price
from app.utils import format_price

portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route('/portfolios/<username>', methods=['GET', 'POST'])
def portfolios_username(username):
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

        # Populate asset lists with current prices from db.
        assets_cache = get_all_assets_dict()

        for tck, amount in data['stocks'].items():
            if tck in assets_cache['stocks']:
                name, price = assets_cache['stocks'][tck]
                if price != "No price data":
                    try:
                        item_price = float(price) * amount / pref_symbol[1]
                        param['stocks'].append({
                            'symbol': tck,
                            'name': name,
                            'number': f"x{amount}",
                            'price': f"{format_price(item_price)}{pref_symbol[0]}"
                        })
                    except ValueError:
                        pass

        for tck, amount in data['crypto'].items():
            if tck in assets_cache['crypto']:
                name, price = assets_cache['crypto'][tck]
                if price != "No price data":
                    try:
                        item_price = float(price) * amount / pref_symbol[1]
                        param['cryptos'].append({
                            'symbol': tck,
                            'name': name,
                            'number': f"x{amount}",
                            'price': f"{format_price(item_price)}{pref_symbol[0]}"
                        })
                    except ValueError:
                        pass

        for tck, amount in data['fiat'].items():
            if tck in assets_cache['fiat']:
                name, price = assets_cache['fiat'][tck]
                if price != "No price data":
                    try:
                        item_price = float(price) * amount / pref_symbol[1]
                        param['fiats'].append({
                            'symbol': tck,
                            'name': name,
                            'number': f"x{amount}",
                            'price': f"{format_price(item_price)}{pref_symbol[0]}"
                        })
                    except ValueError:
                        pass

        # Process portfolio asset updates.
        if request.method == 'POST':
            def handle_asset_update(asset_list, dict_key):
                for asset in asset_list:
                    if request.form.get(f"{dict_key}_{asset['symbol']}_btn"):
                        new_number_str = request.form.get(f"{dict_key}_{asset['symbol']}")
                        try:
                            new_number = float(new_number_str[1:]) if new_number_str.startswith('x') else float(new_number_str)
                        except (ValueError, TypeError):
                            param['danger_btn'] = asset['name']
                            return True
                            
                        pf.set_in_dict(dict_key, asset['symbol'], new_number)
                        old_number = float(asset['number'][1:])
                        if old_number > 0:
                            asset['price'] = f"{format_price((float(asset['price'][:-1]) / old_number) * new_number)}{pref_symbol[0]}"
                        asset['number'] = f"x{new_number}"
                        param['success_btn'] = asset['name']
                        db_sess.commit()
                return False

            if handle_asset_update(param['stocks'], 'stocks'):
                pass
            elif handle_asset_update(param['cryptos'], 'crypto'):
                pass
            else:
                handle_asset_update(param['fiats'], 'fiat')

        # Calculate total portfolio value.
        portfolio_sum = 0
        
        stocks_sum_val = sum([float(i['price'][:-1]) for i in param['stocks']]) if param['stocks'] else 0
        param['stocks_sum'] = f"{format_price(stocks_sum_val)}{pref_symbol[0]}"
        portfolio_sum += stocks_sum_val

        cryptos_sum_val = sum([float(i['price'][:-1]) for i in param['cryptos']]) if param['cryptos'] else 0
        param['cryptos_sum'] = f"{format_price(cryptos_sum_val)}{pref_symbol[0]}"
        portfolio_sum += cryptos_sum_val

        fiats_sum_val = sum([float(i['price'][:-1]) for i in param['fiats']]) if param['fiats'] else 0
        param['fiats_sum'] = f"{format_price(fiats_sum_val)}{pref_symbol[0]}"
        portfolio_sum += fiats_sum_val

        param['portfolio_sum'] = f"{format_price(portfolio_sum)}{pref_symbol[0]}"

    return render_template('portfolios.html', **param)
