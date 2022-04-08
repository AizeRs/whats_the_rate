from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email


class LoginForm(FlaskForm):
    email_or_username = StringField('Электронная почта или логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    email = StringField('Электронная почта', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


class SearchTickerForm(FlaskForm):
    ticker = StringField('Тикер или его начало')
    submit1 = SubmitField('Найти')


class ReloadDataForm(FlaskForm):
    submit2 = SubmitField('Обновить')


class ChangePassForm(FlaskForm):
    old_password = PasswordField('Старый пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired()])
    new_password_submit = PasswordField('Повтор нового пароля', validators=[DataRequired()])
    submit_pass = SubmitField('Сменить пароль')

