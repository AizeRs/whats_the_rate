from sqlalchemy import text

from constants import *
import data_api_functions
import flask_login
from flask import Flask, render_template, redirect, session, url_for, request
from forms import LoginForm, RegisterForm, SearchTickerForm, ReloadDataForm, ChangePassForm
from flask_login import LoginManager, login_user
from data import db_session
from data.users import User
import requests

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
            param['success'] = f'{ticker}_a'

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
            db_sess = db_session.create_session()
            usr = db_sess.query(User).get(flask_login.current_user.id)
            usr.hashed_password = flask_login.current_user.hashed_password
            db_sess.commit()
            param['pass_submit'] = 0
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


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
