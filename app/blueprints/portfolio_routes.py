from flask import Blueprint, render_template, request, url_for
from flask_login import current_user
from data import db_session
from data.users import User
from data.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.file_parser import update_crypto_file, update_currencies_file, save_ticker_price
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
                    update_crypto_file()
                if data['fiat']:
                    update_currencies_file(MAIN_SYMBOLS)

        # Populate asset lists with current prices from local files.
        try:
            with open('list_of_tickers.txt', encoding='utf-8') as stocks_file:
                stocks_content = stocks_file.read().split('\n')
                for line in stocks_content:
                    if not line:
                        continue
                    tck, name, price = line.split(',')
                    if tck in data['stocks']:
                        try:
                            item_price = float(price) * data['stocks'][tck] / pref_symbol[1]
                            param['stocks'].append({
                                'symbol': tck,
                                'name': name,
                                'number': f"x{data['stocks'][tck]}",
                                'price': f"{format_price(item_price)}{pref_symbol[0]}"
                            })
                        except ValueError:
                            pass
        except FileNotFoundError:
            pass

        try:
            with open('list_of_cryptocurrencies.txt', encoding='utf-8') as crypto_file:
                crypto_content = crypto_file.read().split('\n')
                for line in crypto_content:
                    if not line:
                        continue
                    tck, name, price = line.split(',')
                    if tck in data['crypto']:
                        try:
                            item_price = float(price) * data['crypto'][tck] / pref_symbol[1]
                            param['cryptos'].append({
                                'symbol': tck,
                                'name': name,
                                'number': f"x{data['crypto'][tck]}",
                                'price': f"{format_price(item_price)}{pref_symbol[0]}"
                            })
                        except ValueError:
                            pass
        except FileNotFoundError:
            pass

        try:
            with open('list_of_fiat.txt', encoding='utf-8') as fiat_file:
                fiat_content = fiat_file.read().split('\n')
                for line in fiat_content:
                    if not line:
                        continue
                    tck, name, price = line.split(',')
                    if tck in data['fiat']:
                        try:
                            item_price = float(price) * data['fiat'][tck] / pref_symbol[1]
                            param['fiats'].append({
                                'symbol': tck,
                                'name': name,
                                'number': f"x{data['fiat'][tck]}",
                                'price': f"{format_price(item_price)}{pref_symbol[0]}"
                            })
                        except ValueError:
                            pass
        except FileNotFoundError:
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
