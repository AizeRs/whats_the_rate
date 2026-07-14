from flask import Blueprint, render_template, redirect, request
from flask_login import current_user
from forms import SearchTickerForm, ReloadDataForm
from data import db_session
from data.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.file_parser import (
    update_tickers_file, update_crypto_file, update_currencies_file,
    get_stocks_by_letter, get_crypto_by_letter, get_fiat_by_letter,
    save_ticker_price
)
from app.services.api_client import ticker_price
from app.utils import format_price

market_bp = Blueprint('market', __name__)

@market_bp.route('/stocks', methods=['GET', 'POST'])
def stocks():
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {
        'form': form,
        'form2': form2,
        'alphabet': ('abcdefg', 'hijklmn', 'opqrstu', 'vwxyz')
    }

    if form.submit1.data:
        return redirect(f'stocks/{form.ticker.data.upper()}')
    if form2.submit2.data:
        if update_tickers_file():
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_stocks.html', **param)


@market_bp.route('/stocks/<string:letter>', methods=['GET', 'POST'])
def available_stocks_for_letter(letter):
    param = {'letter': letter.upper(), 'stocks': []}
    
    if current_user.is_authenticated:
        main_symbol = current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1.0

    if request.method == 'POST':
        if request.form.get('reload_rate'):
            ticker = request.form.get('reload_rate').split()[-1]
            price_data = ticker_price(ticker)
            if price_data and price_data[0]:
                param['success'] = f'{ticker}_r'
                save_ticker_price(ticker, price_data[0])
            else:
                param['danger'] = f'{ticker}_r'
                
        if request.form.get('add_stock') and current_user.is_authenticated:
            ticker = request.form.get('add_stock').split()[1]
            with db_session.create_session() as db_sess:
                pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
                if not pf:
                    param['danger'] = f'{ticker}_a'
                else:
                    if pf.set_in_dict('stocks', ticker, 1) != 'Too Many Stocks Error':
                        db_sess.commit()
                        param['success'] = f'{ticker}_a'
                    else:
                        param['danger'] = f'{ticker}_a'

    raw_stocks = get_stocks_by_letter(letter)
    for stock in raw_stocks:
        price_val = stock['price']
        if price_val != 'No price data':
            price_val = f"{format_price(float(price_val) / main_rate)}{MAIN_SYMBOLS[main_symbol][0]}"
        param['stocks'].append({'ticker': stock['ticker'], 'stock': stock['stock'], 'price': price_val})
        
    return render_template('available_stocks_for_letter.html', **param)


@market_bp.route('/crypto', methods=['GET', 'POST'])
def crypto():
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {
        'form': form,
        'form2': form2,
        'alphabet': ('abcdefg', 'hijklmn', 'opqrstu', 'vwxyz', '12345', '67890')
    }

    if form.submit1.data:
        return redirect(f'crypto/{form.ticker.data}')
    if form2.submit2.data:
        if update_crypto_file():
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_crypto.html', **param)


@market_bp.route('/crypto/<string:letter>', methods=['GET', 'POST'])
def available_crypto_for_letter(letter):
    param = {'letter': letter.upper(), 'crypto': []}
    
    if current_user.is_authenticated:
        main_symbol = current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1.0

    raw_cryptos = get_crypto_by_letter(letter)
    for crypto in raw_cryptos:
        price_val = f"{format_price(float(crypto['price']) / main_rate)}{MAIN_SYMBOLS[main_symbol][0]}"
        param['crypto'].append({'symbol': crypto['symbol'], 'name': crypto['name'], 'price': price_val})

    if request.method == 'POST':
        if request.form.get('add_crypto') and current_user.is_authenticated:
            ticker = request.form.get('add_crypto').split()[1]
            with db_session.create_session() as db_sess:
                pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
                if not pf:
                    param['danger'] = f'{ticker}_a'
                else:
                    pf.set_in_dict('crypto', ticker, 1)
                    db_sess.commit()
                    param['success'] = f'{ticker}_a'

    return render_template('available_crypto_for_letter.html', **param)


@market_bp.route('/fiat', methods=['GET', 'POST'])
def fiat():
    form = SearchTickerForm()
    form2 = ReloadDataForm()
    param = {
        'form': form,
        'form2': form2
    }

    if form.submit1.data:
        if 'all' not in form.ticker.data and 'main' not in form.ticker.data:
            return redirect(f'fiat/{form.ticker.data}')
    if form2.submit2.data:
        if update_currencies_file(MAIN_SYMBOLS):
            param['reload'] = 1
        else:
            param['reload'] = 2

    return render_template('available_fiat.html', **param)


@market_bp.route('/fiat/<string:letter>', methods=['GET', 'POST'])
def available_fiat_for_letter(letter):
    param = {'letter': letter.upper(), 'fiats': []}
    
    if current_user.is_authenticated:
        main_symbol = current_user.main_currency
        main_rate = MAIN_SYMBOLS[main_symbol][1]
    else:
        main_symbol = 'USD'
        main_rate = 1.0

    raw_fiats = get_fiat_by_letter(letter, MAIN_SYMBOLS.keys())
    for fiat in raw_fiats:
        price_val = f"{format_price(float(fiat['price']) / main_rate)}{MAIN_SYMBOLS[main_symbol][0]}"
        param['fiats'].append({'symbol': fiat['symbol'], 'name': fiat['name'], 'price': price_val})

    if request.method == 'POST':
        if request.form.get('add_fiat') and current_user.is_authenticated:
            ticker = request.form.get('add_fiat').split()[1]
            with db_session.create_session() as db_sess:
                pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
                if not pf:
                    param['danger'] = f'{ticker}_a'
                else:
                    pf.set_in_dict('fiat', ticker, 1)
                    db_sess.commit()
                    param['success'] = f'{ticker}_a'

    return render_template('available_fiat_for_letter.html', **param)
