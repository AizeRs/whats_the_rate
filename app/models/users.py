import sqlalchemy
from .db_session import SqlAlchemyBase
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(SqlAlchemyBase, UserMixin):
    """Represents a registered user in the database."""
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    username = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=True)
    email = sqlalchemy.Column(sqlalchemy.String, index=True, unique=True, nullable=True)
    main_currency = sqlalchemy.Column(sqlalchemy.String, nullable=True, default='USD')
    hashed_password = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    portfolio_id = sqlalchemy.Column(sqlalchemy.Integer)
    apikey = sqlalchemy.Column(sqlalchemy.String, default=None)

    def set_password(self, password):
        """Hashes and sets the user's password."""
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        """Verifies a password against the stored hash."""
        return check_password_hash(self.hashed_password, password)
