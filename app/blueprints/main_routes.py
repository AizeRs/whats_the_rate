from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user, login_required
from app.forms import ChangePassForm, CreatePortfolio
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio
from app.services.symbols import MAIN_SYMBOLS
import secrets

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/index')
def index():
    """Renders the main index page."""
    return render_template('index.html')


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
        flag = False

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
