import secrets
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_user, logout_user, current_user
from flask_wtf.csrf import validate_csrf
from wtforms import ValidationError
from sqlalchemy import func
from app.forms import LoginForm, RegisterForm
from app.models import db_session
from app.models.users import User
from app.models.portfolios import Portfolio

auth_bp = Blueprint('auth', __name__)

# Shared demo account: entered only with the button on the sign-in page
DEMO_USERNAME = 'demo'
DEMO_PORTFOLIO = {'stocks': {'AAPL': 5, 'NVDA': 5, 'MSFT': 5},
                  'crypto': {'BTC': 0.05, 'ETH': 1, 'SOL': 5},
                  'fiat': {'EUR': 500, 'GBP': 500}}

def _render_auth(mode, login_form=None, register_form=None, message=None):
    """Login and registration live on one page (auth.html); `mode` picks the form shown first."""
    return render_template('auth.html', mode=mode, message=message,
                           login_form=login_form or LoginForm(),
                           register_form=register_form or RegisterForm(prefix='reg'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login authentication."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        with db_session.create_session() as db_sess:
            email_or_username = form.email_or_username.data.strip()
            if '@' in email_or_username:
                user = db_sess.query(User).filter(User.email == email_or_username).first()
            else:
                user = db_sess.query(User).filter(User.username == email_or_username).first()

            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                return redirect(url_for("main.index"))

            return _render_auth('login', login_form=form, message="Неправильный логин или пароль")
    return _render_auth('login', login_form=form)


@auth_bp.route('/login/demo', methods=['POST'])
def demo_login():
    """Signs in to the shared demo account (created with a filled public portfolio on first use)."""
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        return redirect(url_for('auth.login'))
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).filter(User.username == DEMO_USERNAME).first()
        if not user:
            portfolio = Portfolio(isprivate=False, contains=DEMO_PORTFOLIO)
            db_sess.add(portfolio)
            db_sess.flush()
            user = User(username=DEMO_USERNAME, email='demo@example.com', portfolio_id=portfolio.id)
            user.set_password(secrets.token_urlsafe(32))
            db_sess.add(user)
            db_sess.commit()
        login_user(user, remember=False)
    return redirect(url_for('main.index'))


@auth_bp.route('/logout')
def logout():
    """Logs out the current user."""
    logout_user()
    return redirect(url_for("main.index"))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # Prefix keeps field ids/names apart from the login form on the same page
    form = RegisterForm(prefix='reg')
    if form.validate_on_submit():
        with db_session.create_session() as db_sess:
            email = form.email.data.strip()
            username = form.username.data.strip()

            if db_sess.query(User).filter(User.email == email).first():
                form.email.errors.append("Данный адрес электронной почты уже занят")
                return _render_auth('register', register_form=form)

            if username.lower() == DEMO_USERNAME or \
                    db_sess.query(User).filter(func.lower(User.username) == username.lower()).first():
                form.username.errors.append("Данное имя пользователя уже занято")
                return _render_auth('register', register_form=form)

            user = User(email=email, username=username)
            user.set_password(form.password.data)
            db_sess.add(user)
            db_sess.commit()

            # Authenticate the newly registered user.
            login_user(user, remember=True)
            return redirect(url_for("main.index"))

    return _render_auth('register', register_form=form)
