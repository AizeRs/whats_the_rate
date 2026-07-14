from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_user, logout_user, current_user
from forms import LoginForm, RegisterForm
from data import db_session
from data.users import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
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
                
            return render_template('login.html',
                                   message="Неправильный логин или пароль",
                                   form=form)
    return render_template('login.html', title='Авторизация', form=form)


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RegisterForm()
    if form.validate_on_submit():
        with db_session.create_session() as db_sess:
            email = form.email.data.strip()
            username = form.username.data.strip()
            
            if db_sess.query(User).filter(User.email == email).first():
                form.email.errors.append("Данный адрес электронной почты уже занят")
                return render_template('register.html', title='Авторизация', form=form)
                
            if db_sess.query(User).filter(User.username == username).first():
                form.username.errors.append("Данное имя пользователя уже занято")
                return render_template('register.html', title='Авторизация', form=form)
                
            if "@" in username:
                form.username.errors.append('Имя пользователя не должно содержать символ "@"')
                return render_template('register.html', title='Авторизация', form=form)
                
            if len(form.password.data) < 5:
                form.password.errors.append("Минимальная длина пароля - 5 символов")
                return render_template('register.html', title='Авторизация', form=form)
                
            user = User(email=email, username=username)
            user.set_password(form.password.data)
            db_sess.add(user)
            db_sess.commit()
            
            # Authenticate the newly registered user.
            login_user(user, remember=True)
            return redirect(url_for("main.index"))
            
    return render_template('register.html', title='Авторизация', form=form)
