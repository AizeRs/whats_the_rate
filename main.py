from constants import *
import data_api_functions
import flask_login
from flask import Flask, render_template, redirect, session, url_for, request
from forms import LoginForm, RegisterForm, SearchTickerForm, ReloadDataForm
from flask_login import LoginManager, login_user
from data import db_session
from data.users import User
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
login_manager = LoginManager()
login_manager.init_app(app)

db_session.global_init('db/users.db')


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

    if request.method == 'POST':
        if request.form.get('reload_rate'):
            ticker = request.form.get('reload_rate').split()[-1]
            price = data_api_functions.ticker_price(ticker)
            if price:
                param['success'] = f'{ticker}_r'
                data_api_functions.save_ticker_price(ticker, price[0])
            else:
                param['danger'] = f'{ticker}_r'
        if request.form.get('add_stock'):
            ticker = request.form.get('add_stock').split()[1]
            param['success'] = f'{ticker}_a'
            print(f'add_stock: {ticker}')

    with open('list_of_tickers.txt', 'r', encoding='utf-8') as file:
        stocks = file.read()
        for line in stocks.split('\n')[1:]:
            if not line.startswith(letter.upper()):
                continue
            if not line:
                continue
            ticker, stock, price = line.split(',')
            param['stocks'].append({'ticker': ticker, 'stock': stock, 'price': price})
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
    with open('list_of_cryptocurrencies.txt', 'r', encoding='utf-8') as file:
        crypto = file.read()
        if letter.isupper():
            print('upper')
            for line in crypto.split('\n'):
                if not line.startswith(letter):
                    continue
                if not line:
                    continue
                symbol, name, price = line.split(',')
                param['crypto'].append({'symbol': symbol, 'name': name, 'price': price})
        else:
            for line in crypto.split('\n'):
                if not line:
                    continue
                symbol, name, price = line.split(',')
                if not name.startswith(letter):
                    continue
                param['crypto'].append({'symbol': symbol, 'name': name, 'price': price})
    return render_template('available_crypto_for_letter.html', **param)


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


@app.route('/user')
def user():
    return "user's account will be here"


@app.route('/fiat')
def fiat():
    return "fiat currencies will be here"


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
