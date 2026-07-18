from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class LoginForm(FlaskForm):
    """Form for user authentication."""
    email_or_username = StringField('Электронная почта или логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    """Form for new user registration."""
    username = StringField('Логин', validators=[DataRequired()])
    email = StringField('Электронная почта', validators=[DataRequired(), Email(message="Некорректный email")])
    password = PasswordField('Пароль', validators=[
        DataRequired(), 
        Length(min=5, message="Минимальная длина пароля - 5 символов")
    ])
    submit = SubmitField('Зарегистрироваться')


class SearchTickerForm(FlaskForm):
    """Form for searching financial tickers."""
    ticker = StringField('Тикер или его начало')
    submit1 = SubmitField('Найти')


class ReloadDataForm(FlaskForm):
    """Form to trigger data reloading/refreshing."""
    submit2 = SubmitField('Обновить')


class ChangePassForm(FlaskForm):
    """Form for changing user password."""
    old_password = PasswordField('Старый пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[
        DataRequired(),
        Length(min=5, message="Минимальная длина пароля - 5 символов")
    ])
    new_password_submit = PasswordField('Повтор нового пароля', validators=[
        DataRequired(),
        EqualTo('new_password', message="Пароли не совпадают")
    ])
    submit_pass = SubmitField('Сменить пароль')


class CreatePortfolio(FlaskForm):
    """Form for creating a new portfolio."""
    submit_private = SubmitField('Создать приватный портфель только для Вас')
    submit_public = SubmitField('Создать публичный портфель с доступом по ссылке')
