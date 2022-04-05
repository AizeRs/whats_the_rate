from constants import *
import data_api_functions
import flask_login
from flask import Flask, render_template, redirect, url_for
from forms import LoginForm, RegisterForm
from flask_login import LoginManager, login_user
from data import db_session
from data.users import User

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


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
