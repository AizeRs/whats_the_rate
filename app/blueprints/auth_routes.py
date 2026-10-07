from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_user, logout_user, current_user
from app.forms import LoginForm, RegisterForm
from app.models import db_session
from app.models.users import User

auth_bp = Blueprint('auth', __name__)

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

            if db_sess.query(User).filter(User.username == username).first():
                form.username.errors.append("Данное имя пользователя уже занято")
                return _render_auth('register', register_form=form)

            if "@" in username:
                form.username.errors.append('Имя пользователя не должно содержать символ "@"')
                return _render_auth('register', register_form=form)

            user = User(email=email, username=username)
            user.set_password(form.password.data)
            db_sess.add(user)
            db_sess.commit()

            # Authenticate the newly registered user.
            login_user(user, remember=True)
            return redirect(url_for("main.index"))

    return _render_auth('register', register_form=form)
