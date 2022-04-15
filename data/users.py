import sqlalchemy
from .db_session import SqlAlchemyBase
from flask_login import UserMixin
from hashlib import sha256


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    username = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=True)
    email = sqlalchemy.Column(sqlalchemy.String, index=True, unique=True, nullable=True)
    main_currency = sqlalchemy.Column(sqlalchemy.String, nullable=True, default='USD')
    hashed_password = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    portfolio_id = sqlalchemy.Column(sqlalchemy.Integer)

    def set_password(self, password):
        self.hashed_password = sha256(str(password).encode('utf-8')).hexdigest()

    def check_password(self, password):
        return self.hashed_password == sha256(str(password).encode('utf-8')).hexdigest()
