from constants import *
import data_api_functions
import flask_login
from flask import Flask, render_template, redirect, session, url_for, request
from forms import *
from flask_login import LoginManager, login_user
from data import db_session
from data.users import User
from data.portfolios import Portfolio
from random import randint

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
login_manager = LoginManager()
login_manager.init_app(app)

db_session.global_init('db/users.db')

MAIN_SYMBOLS = {'USD': ('$', 0), 'EUR': ('€', 0), 'RUB': ('₽', 0), 'GBP': ('£', 0), 'JPY': ('¥', 0), 'CHF': ('₣', 0),
                'BTC': ('₿', 0)}

with open('list_of_fiat.txt', 'r', encoding='utf-8') as file:
    fiats = file.read()
    for line in fiats.split('\n'):
        if not line:
            continue
        symbol, name, cur_price = line.split(',')
        if symbol in MAIN_SYMBOLS.keys():
            MAIN_SYMBOLS[symbol] = (MAIN_SYMBOLS[symbol][0], float(cur_price))
    del (symbol, name, cur_price, line, fiats)


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.route('/')
@app.route('/index')
def index():
    param = {}
    return render_template('index.html', **param)


@app.route('/stocks', methods=['GET', 'POST'])
def stocks():
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {}
    param['form'] = form
    param['form2'] = form2
    param['alphabet'] = ('abcdefg', 'hijklmn', 'opqrstu', 'vwxyz')

    if form.submit1.data:
        return redirect(f'stocks/{form.ticker.data.upper()}')
    if form2.submit2.data:
        if data_api_functions.update_tickers_file():
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_stocks.html', **param)


@app.route('/stocks/<string:letter>', methods=['GET', 'POST'])
def available_stocks_for_letter(letter):
    param = {}
    param['letter'] = letter.upper()
    param['stocks'] = []
    if flask_login.current_user.is_authenticated:
        main_symbol = flask_login.current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1
    if request.method == 'POST':
        if request.form.get('reload_rate'):
            ticker = request.form.get('reload_rate').split()[-1]
            price = data_api_functions.ticker_price(ticker)[0]
            if price:
                param['success'] = f'{ticker}_r'
                data_api_functions.save_ticker_price(ticker, price)
            else:
                param['danger'] = f'{ticker}_r'
        if request.form.get('add_stock'):
            ticker = request.form.get('add_stock').split()[1]
            db_sess = db_session.create_session()
            pf = db_sess.query(Portfolio).filter(Portfolio.id == flask_login.current_user.portfolio_id)
            if not pf:
                param['danger'] = f'{ticker}_a'
            else:
                pf = pf.one()
                if pf.set_in_dict('stocks', ticker, 1) != 'Too Many Stocks Error':
                    db_sess.commit()
                    param['success'] = f'{ticker}_a'
                else:
                    param['danger'] = f'{ticker}_a'

    with open('list_of_tickers.txt', 'r', encoding='utf-8') as file:
        stocks = file.read()
        for line in stocks.split('\n')[1:]:
            if not line.startswith(letter.upper()):
                continue
            if not line:
                continue
            ticker, stock, price = line.split(',')
            param['stocks'].append({'ticker': ticker, 'stock': stock,
                                    'price': str(float(price) / main_rate) + MAIN_SYMBOLS[main_symbol][0]
                                    if price != 'No price data' else price})
    return render_template('available_stocks_for_letter.html', **param)


@app.route('/crypto', methods=['GET', 'POST'])
def crypto():
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {}
    param['form'] = form
    param['form2'] = form2
    param['alphabet'] = ('abcdefg', 'hijklmn', 'opqrstu', 'vwxyz', '12345', '67890')

    if form.submit1.data:
        return redirect(f'crypto/{form.ticker.data}')
    if form2.submit2.data:
        if data_api_functions.update_crypto_file():
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_crypto.html', **param)


@app.route('/crypto/<string:letter>', methods=['GET', 'POST'])
def available_crypto_for_letter(letter):
    param = {}
    param['letter'] = letter.upper()
    param['crypto'] = []
    if flask_login.current_user.is_authenticated:
        main_symbol = flask_login.current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1
    with open('list_of_cryptocurrencies.txt', 'r', encoding='utf-8') as file:
        crypto = file.read()
        if letter.isupper():
            for line in crypto.split('\n'):
                if not line.startswith(letter):
                    continue
                if not line:
                    continue
                symbol, name, price = line.split(',')
                param['crypto'].append({'symbol': symbol, 'name': name,
                                        'price': str(float(price) / main_rate) + MAIN_SYMBOLS[main_symbol][0]})
        else:
            for line in crypto.split('\n'):
                if not line:
                    continue
                symbol, name, price = line.split(',')
                if not name.startswith(letter):
                    continue
                param['crypto'].append({'symbol': symbol, 'name': name,
                                        'price': str(float(price) / main_rate) + MAIN_SYMBOLS[main_symbol][0]})

    if request.method == 'POST':
        if request.form.get('add_crypto'):
            ticker = request.form.get('add_crypto').split()[1]
            db_sess = db_session.create_session()
            pf = db_sess.query(Portfolio).filter(Portfolio.id == flask_login.current_user.portfolio_id)
            if not pf:
                param['danger'] = f'{ticker}_a'
                return
            pf = pf.one()
            pf.set_in_dict('crypto', ticker, 1)
            db_sess.commit()
            param['success'] = f'{ticker}_a'

    return render_template('available_crypto_for_letter.html', **param)


@app.route('/fiat', methods=['GET', 'POST'])
def fiat():
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {}
    param['form'] = form
    param['form2'] = form2

    if form.submit1.data:
        if 'all' not in form.ticker.data and 'main' not in form.ticker.data:
            return redirect(f'fiat/{form.ticker.data}')
    if form2.submit2.data:
        if data_api_functions.update_currencies_file():
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_fiat.html', **param)


@app.route('/fiat/<string:letter>', methods=['GET', 'POST'])
def available_fiat_for_letter(letter):
    param = {}
    param['letter'] = letter.upper()
    param['fiats'] = []
    if flask_login.current_user.is_authenticated:
        main_symbol = flask_login.current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1
    with open('list_of_fiat.txt', 'r', encoding='utf-8') as file:
        fiats = file.read()
        if letter.isupper():
            for line in fiats.split('\n'):
                if not line.startswith(letter):
                    continue
                if line.startswith('BTC'):
                    continue
                if not line:
                    continue
                symbol, name, price = line.split(',')
                param['fiats'].append({'symbol': symbol, 'name': name,
                                       'price': str(float(price) / main_rate) + MAIN_SYMBOLS[main_symbol][0]})
        elif letter == 'main':
            for line in fiats.split('\n'):
                if not line:
                    continue
                if line.startswith('BTC'):
                    continue
                symbol, name, price = line.split(',')
                if symbol not in MAIN_SYMBOLS.keys():
                    continue
                param['fiats'].append({'symbol': symbol, 'name': name,
                                       'price': str(float(price) / main_rate) + MAIN_SYMBOLS[main_symbol][0]})
        else:
            for line in fiats.split('\n'):
                if not line:
                    continue
                if line.startswith('BTC'):
                    continue
                symbol, name, price = line.split(',')
                if not name.startswith(letter) and letter != 'all':
                    continue
                param['fiats'].append({'symbol': symbol, 'name': name,
                                       'price': str(float(price) / main_rate) + MAIN_SYMBOLS[main_symbol][0]})

        if request.form.get('add_fiat'):
            ticker = request.form.get('add_fiat').split()[1]
            db_sess = db_session.create_session()
            pf = db_sess.query(Portfolio).filter(Portfolio.id == flask_login.current_user.portfolio_id)
            if not pf:
                param['danger'] = f'{ticker}_a'
                return
            pf = pf.one()
            pf.set_in_dict('fiat', ticker, 1)
            db_sess.commit()
            param['success'] = f'{ticker}_a'

    return render_template('available_fiat_for_letter.html', **param)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        if '@' in form.email_or_username.data.strip():
            user = db_sess.query(User).filter(User.email == form.email_or_username.data.strip()).first()
        else:
            user = db_sess.query(User).filter(User.username == form.email_or_username.data.strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("index")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
def logout():
    flask_login.logout_user()
    return redirect(url_for("index"))


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = User()
        user.email = form.email.data.strip()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            form.email.errors.append("Данный адрес электронной почты уже занят")
            return render_template('register.html', title='Авторизация', form=form)
        user.username = form.username.data.strip()
        if db_sess.query(User).filter(User.username == form.username.data).first():
            form.username.errors.append("Данное имя пользователя уже занято")
            return render_template('register.html', title='Авторизация', form=form)
        if "@" in form.username.data:
            form.username.errors.append('Имя пользователя не должно содержать символ "@"')
            return render_template('register.html', title='Авторизация', form=form)
        user.set_password(form.password.data)
        if len(form.password.data) < 5:
            form.password.errors.append("Минимальная длина пароля - 5 символов")
            return render_template('register.html', title='Авторизация', form=form)
        db_sess.add(user)
        db_sess.commit()
        login_user(user, remember=True)
        return redirect("./index")
    return render_template('register.html', title='Авторизация', form=form)


@app.route('/user', methods=['GET', 'POST'])
def user():
    if not flask_login.current_user.is_authenticated:
        return redirect(url_for('login'))

    pass_form = ChangePassForm()
    param = {}
    param['pass_form'] = pass_form
    param['main_currencies'] = [(i, MAIN_SYMBOLS[i][0]) for i in MAIN_SYMBOLS.keys()]
    if not flask_login.current_user.portfolio_id:
        portfolio_form = CreatePortfolio()
        param['portfolio_form_'] = portfolio_form
        param['portfolio_form'] = portfolio_form
        flag = True
    else:
        param['user_portfolio_link'] = url_for(f'portfolios_username', username=flask_login.current_user.username)
        flag = False
    db_sess = db_session.create_session()

    if request.method == 'POST':
        if request.form.get('create_apikey') and flask_login.current_user.apikey is None:
            apikey = randint(1000000000000000, 9999999999999999)
            usr = db_sess.query(User).filter(User.id == flask_login.current_user.id).one()
            usr.apikey = apikey
            flask_login.current_user.apikey = apikey
            db_sess.commit()
    if pass_form.submit_pass.data:
        if not flask_login.current_user.check_password(pass_form.old_password.data):
            pass_form.old_password.errors = ['Неверный пароль']
            param['pass_submit'] = 1
        elif len(pass_form.new_password.data) < 5:
            pass_form.new_password.errors = ['Минимальная длина пароля - 5 символов']
            param['pass_submit'] = 1
        elif pass_form.new_password.data != pass_form.new_password_submit.data:
            pass_form.new_password_submit.errors = ['Пароли не совпадают']
            param['pass_submit'] = 1
        else:
            flask_login.current_user.set_password(pass_form.new_password.data)
            usr = db_sess.query(User).get(flask_login.current_user.id)
            usr.hashed_password = flask_login.current_user.hashed_password
            db_sess.commit()
            param['pass_submit'] = 0
    if not flask_login.current_user.portfolio_id:
        if flag and portfolio_form.submit_private.data:
            pf = Portfolio(isprivate=True)
        if flag and portfolio_form.submit_public.data:
            pf = Portfolio(isprivate=False)

        if flag and (portfolio_form.submit_private.data or portfolio_form.submit_public.data):
            db_sess = db_session.create_session()
            user = db_sess.query(User).get(flask_login.current_user.id)
            db_sess.add(pf)
            ids = [i[0] for i in db_sess.query(Portfolio.id).all()]
            user.portfolio_id = max(ids) if ids else 1
            db_sess.commit()
    return render_template('user.html', **param)


@app.route('/user/set_main_currency/<string:currency>')
def user_set_main_currency(currency):
    if currency not in MAIN_SYMBOLS.keys():
        return redirect(url_for('user'))
    if not flask_login.current_user.is_authenticated:
        return redirect(url_for('login'))

    db_sess = db_session.create_session()
    usr = db_sess.query(User).get(flask_login.current_user.id)
    usr.main_currency = currency
    db_sess.commit()
    flask_login.current_user.main_currency = currency
    return redirect(url_for('user'))


@app.route('/portfolios/<username>', methods=['GET', 'POST'])
def portfolios_username(username):
    param = {}
    db_sess = db_session.create_session()

    user = db_sess.query(User).filter(User.username == username).all()
    if not user:
        return render_template('portfolios.html')
    user = user[0]

    pf = db_sess.query(Portfolio).filter(Portfolio.id == user.portfolio_id)
    if not pf:
        param['not_found'] = True
        return render_template('portfolios.html')
    pf = pf.one()

    if pf.isprivate and (not flask_login.current_user.is_authenticated or flask_login.current_user.id != user.id):
        param['no_access'] = True
    param['username'] = username

    if flask_login.current_user.is_authenticated:
        pref_symbol = MAIN_SYMBOLS[flask_login.current_user.main_currency]
        if flask_login.current_user.id == user.id:
            param['is_owner'] = True
    else:
        pref_symbol = MAIN_SYMBOLS['USD']
    data = pf.get_dict()

    if request.method == 'POST':
        if request.form.get('reload'):
            for ticker in data['stocks'].keys():
                price = data_api_functions.ticker_price(ticker)[0]
                if price:
                    param['success_btn'] = 'reload'
                    data_api_functions.save_ticker_price(ticker, price)
                else:
                    param['danger_btn'] = 'reload'
            if data['crypto']:
                data_api_functions.update_crypto_file()
            if data['fiat']:
                data_api_functions.update_currencies_file()

    param['stocks'] = []
    param['cryptos'] = []
    param['fiats'] = []
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
                        param['stocks'].append({'symbol': current_stock,
                                                'name': name,
                                                'number': 'x' + str(data['stocks'][current_stock]),
                                                'price': str(float(price) * data['stocks'][current_stock]
                                                             / pref_symbol[1]) + pref_symbol[0]
                                                })
                    except ValueError:
                        continue

        for line in crypto_file.read().split('\n'):
            if not line:
                continue
            for current_crypto in data['crypto'].keys():
                tck, name, price = line.split(',')
                if tck == current_crypto:
                    try:
                        param['cryptos'].append({'symbol': current_crypto,
                                                 'name': name,
                                                 'number': 'x' + str(data['crypto'][current_crypto]),
                                                 'price': str(float(price) * data['crypto'][current_crypto]
                                                              / pref_symbol[1]) + pref_symbol[0]
                                                 })
                    except ValueError:
                        continue

        for line in fiat_file.read().split('\n'):
            if not line:
                continue
            for current_fiat in data['fiat'].keys():
                tck, name, price = line.split(',')
                if tck == current_fiat:
                    try:
                        param['fiats'].append({'symbol': current_fiat,
                                               'name': name,
                                               'number': 'x' + str(data['fiat'][current_fiat]),
                                               'price': str(float(price) * data['fiat'][current_fiat]
                                                            / pref_symbol[1]) + pref_symbol[0]
                                               })
                    except ValueError:
                        continue

    if request.method == 'POST':
        for stock in param['stocks']:
            if request.form.get(f"stocks_{stock['symbol']}_btn"):
                new_number = request.form.get(f"stocks_{stock['symbol']}")
                try:
                    new_number = float(new_number[1:]) if new_number.startswith('x') else float(new_number)
                except (ValueError, TypeError):
                    param['danger_btn'] = stock['name']
                    break

                pf.set_in_dict('stocks', stock['symbol'], new_number)
                param['stocks'][param['stocks'].index(stock)]['price'] = str(
                    float(stock['price'][:-1]) / float(stock['number'][1:]) * new_number) + pref_symbol[0]
                param['stocks'][param['stocks'].index(stock)]['number'] = 'x' + str(new_number)
                param['success_btn'] = stock['name']
                db_sess.commit()

        for crypto in param['cryptos']:
            if request.form.get(f"crypto_{crypto['symbol']}_btn"):
                new_number = request.form.get(f"crypto_{crypto['symbol']}")
                try:
                    new_number = float(new_number[1:]) if new_number.startswith('x') else float(new_number)
                except (ValueError, TypeError):
                    param['danger_btn'] = crypto['name']
                    break

                pf.set_in_dict('crypto', crypto['symbol'], new_number)
                param['cryptos'][param['cryptos'].index(crypto)]['price'] = str(
                    float(crypto['price'][:-1]) / float(crypto['number'][1:]) * new_number) + pref_symbol[0]
                param['cryptos'][param['cryptos'].index(crypto)]['number'] = 'x' + str(new_number)
                param['success_btn'] = crypto['name']
                db_sess.commit()

        for fiat in param['fiats']:
            if request.form.get(f"fiat_{fiat['symbol']}_btn"):
                new_number = request.form.get(f"fiat_{fiat['symbol']}")
                try:
                    new_number = float(new_number[1:]) if new_number.startswith('x') else float(new_number)
                except (ValueError, TypeError):
                    param['danger_btn'] = fiat['name']
                    break

                pf.set_in_dict('fiat', fiat['symbol'], new_number)
                param['fiats'][param['fiats'].index(fiat)]['price'] = str(
                    float(fiat['price'][:-1]) / float(fiat['number'][1:]) * new_number) + pref_symbol[0]
                param['fiats'][param['fiats'].index(fiat)]['number'] = 'x' + str(new_number)
                param['success_btn'] = fiat['name']
                db_sess.commit()

    param['portfolio_sum'] = 0
    param['stocks_sum'] = '0'
    param['fiats_sum'] = '0'
    param['cryptos_sum'] = '0'

    if param['stocks']:
        param['portfolio_sum'] += sum([float(i['price'][:-1]) for i in param['stocks']])
        param['stocks_sum'] = str(sum([float(i['price'][:-1]) for i in param['stocks']]))
    param['stocks_sum'] = param['stocks_sum'] + pref_symbol[0]

    if param['cryptos']:
        param['portfolio_sum'] += sum([float(i['price'][:-1]) for i in param['cryptos']])
        param['cryptos_sum'] = str(sum([float(i['price'][:-1]) for i in param['cryptos']]))
    param['cryptos_sum'] = param['cryptos_sum'] + pref_symbol[0]

    if param['fiats']:
        param['portfolio_sum'] += sum([float(i['price'][:-1]) for i in param['fiats']])
        param['fiats_sum'] = str(sum([float(i['price'][:-1]) for i in param['fiats']]))
    param['fiats_sum'] = param['fiats_sum'] + pref_symbol[0]
    param['portfolio_sum'] = str(param['portfolio_sum']) + pref_symbol[0]

    return render_template('portfolios.html', **param)


if __name__ == '__main__':
    import api
    app.register_blueprint(api.blueprint)
    try:
        app.run(port=PORT, host=HOST)
    except OSError:
        app.run(port=8080, host='localhost')
