from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo

REQUIRED = "Заполните это поле"


class LoginForm(FlaskForm):
    """Form for user authentication."""
    email_or_username = StringField('Электронная почта или логин', validators=[DataRequired(message=REQUIRED)])
    password = PasswordField('Пароль', validators=[DataRequired(message=REQUIRED)])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    """Form for new user registration."""
    username = StringField('Логин', validators=[DataRequired(message=REQUIRED)])
    email = StringField('Электронная почта', validators=[DataRequired(message=REQUIRED), Email(message="Некорректный email")])
    password = PasswordField('Пароль', validators=[
        DataRequired(message=REQUIRED), 
        Length(min=5, message="Минимальная длина пароля - 5 символов")
    ])
    submit = SubmitField('Зарегистрироваться')


class ChangePassForm(FlaskForm):
    """Form for changing user password."""
    old_password = PasswordField('Старый пароль', validators=[DataRequired(message=REQUIRED)])
    new_password = PasswordField('Новый пароль', validators=[
        DataRequired(message=REQUIRED),
        Length(min=5, message="Минимальная длина пароля - 5 символов")
    ])
    new_password_submit = PasswordField('Повтор нового пароля', validators=[
        DataRequired(message=REQUIRED),
        EqualTo('new_password', message="Пароли не совпадают")
    ])
    submit_pass = SubmitField('Сменить пароль')


class CreatePortfolio(FlaskForm):
    """Form for creating a new portfolio."""
    submit_private = SubmitField('Создать приватный портфель только для Вас')
    submit_public = SubmitField('Создать публичный портфель с доступом по ссылке')


class PortfolioVisibility(FlaskForm):
    """Form for switching an existing portfolio between private and public."""
    make_private = SubmitField('Приватный')
    make_public = SubmitField('Публичный')
