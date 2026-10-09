from flask import Blueprint, render_template, redirect, url_for, request, send_from_directory, current_app, jsonify, get_template_attribute
from flask_login import current_user, login_required
from app.forms import ChangePassForm, CreatePortfolio, PortfolioVisibility
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
from app.services.data_service import get_stocks_by_tickers, save_ticker_price, save_stock_market_cap
from app.services.api_client import fetch_quote, fetch_stock_market_cap
from app.blueprints.portfolio_routes import portfolio_summary
from app.blueprints import market_routes
from app import home
from datetime import datetime
import os
import secrets

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET', 'POST'])
@main_bp.route('/index', methods=['GET', 'POST'])
def index():
    """Home page: quotes of three markets for everyone, the portfolio summary for a signed-in user."""
    if request.method == 'POST':
        # The page asks to reload an outdated price of one of its stocks
        ticker = (request.get_json(silent=True) or {}).get('refresh_stock')
        if ticker not in home.STOCKS:
            return jsonify({'success': False, 'status': 'error'}), 400
        stock = next(iter(get_stocks_by_tickers([ticker])), None)
        # The price is reloaded only when it's old; the market cap — when it's missing or a day old
        status = 'ok'
        if stock is None or home.stock_home_row(stock)['stale']:
            status, quote = fetch_quote(ticker)
            if status == 'ok':
                save_ticker_price(ticker, quote['c'], quote.get('dp'))
        if status == 'ok' and (stock is None or home.market_cap_is_stale(stock)):
            cap = fetch_stock_market_cap(ticker)
            if cap:
                save_stock_market_cap(ticker, cap)
                home.market_cap_loaded(ticker)
        stock = next(iter(get_stocks_by_tickers([ticker])), None)
        html = ''
        if stock:
            html = str(get_template_attribute('_home_macros.html', 'stock_row')(home.stock_home_row(stock)))
        return jsonify({'success': status == 'ok', 'status': status, 'html': html})

    markets = home.home_markets()
    # Old crypto / fiat quotes are reloaded by the page itself, with the same retry limits as on their own pages
    now = datetime.now()
    auto_crypto = markets['crypto_stale'] and not (
        market_routes._crypto_last_auto_attempt
        and now - market_routes._crypto_last_auto_attempt < market_routes._CRYPTO_AUTO_RETRY_AFTER)
    if auto_crypto:
        market_routes._crypto_last_auto_attempt = now
    auto_fiat = markets['fiat_stale'] and not (
        market_routes._fiat_last_auto_attempt
        and now - market_routes._fiat_last_auto_attempt < market_routes._FIAT_AUTO_RETRY_AFTER)
    if auto_fiat:
        market_routes._fiat_last_auto_attempt = now

    summary = None
    if current_user.is_authenticated and current_user.portfolio_id:
        with db_session.create_session() as db_sess:
            pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
            data = pf.get_dict() if pf else {}
        summary = portfolio_summary(data)
    return render_template('index.html', markets=markets, summary=summary, auto_crypto=auto_crypto,
                           auto_fiat=auto_fiat, greeting=home.greeting() if current_user.is_authenticated else None)


@main_bp.route('/favicon.ico')
def favicon():
    """Browsers request /favicon.ico at the root even without a <link>."""
    return send_from_directory(os.path.join(current_app.static_folder, 'img', 'logo'), 'favicon.ico')


@main_bp.route('/user', methods=['GET', 'POST'])
@login_required
def user():
    """Handles user profile page, password changes, and portfolio creation."""
    pass_form = ChangePassForm()
    param = {
        'pass_form': pass_form,
        'main_currencies': [(i, MAIN_SYMBOLS[i][0]) for i in MAIN_SYMBOLS.keys()]
    }
    
    flag = False
    if not current_user.portfolio_id:
        portfolio_form = CreatePortfolio()
        param['portfolio_form_'] = portfolio_form
        param['portfolio_form'] = portfolio_form
        flag = True
    else:
        param['user_portfolio_link'] = url_for('portfolio.portfolios_username', username=current_user.username)
        param['visibility_form'] = visibility_form = PortfolioVisibility()
        flag = False

        # Switch an existing portfolio between private and public
        if request.method == 'POST' and (visibility_form.make_private.data or visibility_form.make_public.data):
            if visibility_form.validate():
                with db_session.create_session() as db_sess:
                    pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
                    if pf:
                        pf.isprivate = bool(visibility_form.make_private.data)
                        db_sess.commit()
            return redirect(url_for('main.user'))

        with db_session.create_session() as db_sess:
            pf = db_sess.query(Portfolio).filter(Portfolio.id == current_user.portfolio_id).first()
            param['portfolio_private'] = bool(pf and pf.isprivate)

    if request.method == 'POST':
        with db_session.create_session() as db_sess:
            if request.form.get('create_apikey') and current_user.apikey is None:
                apikey = secrets.token_hex(16)
                usr = db_sess.query(User).get(current_user.id)
                usr.apikey = apikey
                db_sess.commit()
                current_user.apikey = apikey
                
            if pass_form.submit_pass.data:
                if pass_form.validate():
                    if not current_user.check_password(pass_form.old_password.data):
                        pass_form.old_password.errors = ['Неверный пароль']
                        param['pass_submit'] = 1
                    else:
                        usr = db_sess.query(User).get(current_user.id)
                        usr.set_password(pass_form.new_password.data)
                        db_sess.commit()
                        current_user.hashed_password = usr.hashed_password
                        param['pass_submit'] = 0
                else:
                    param['pass_submit'] = 1

            if not current_user.portfolio_id:
                if flag and portfolio_form.submit_private.data:
                    pf = Portfolio(isprivate=True)
                if flag and portfolio_form.submit_public.data:
                    pf = Portfolio(isprivate=False)
        
                if flag and (portfolio_form.submit_private.data or portfolio_form.submit_public.data):
                    user = db_sess.query(User).get(current_user.id)
                    db_sess.add(pf)
                    # Flush to generate ID before assignment to user
                    db_sess.flush()
                    user.portfolio_id = pf.id
                    db_sess.commit()

    return render_template('user.html', **param)


@main_bp.route('/user/set_main_currency/<string:currency>')
@login_required
def user_set_main_currency(currency):
    """Updates the user's preferred main currency."""
    if currency not in MAIN_SYMBOLS.keys():
        return redirect(url_for('main.user'))

    with db_session.create_session() as db_sess:
        usr = db_sess.query(User).get(current_user.id)
        usr.main_currency = currency
        db_sess.commit()
        current_user.main_currency = currency
        
    return redirect(url_for('main.user'))
