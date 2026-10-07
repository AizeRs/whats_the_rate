from flask import Flask
from flask_login import LoginManager
from app.constants import SECRET_KEY
from app.models import db_session
from app.models.users import User
from app.services.symbols import MAIN_SYMBOLS

login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    """Loads a user from the database by their ID."""
    with db_session.create_session() as db_sess:
        user = db_sess.query(User).get(user_id)
        if user and user.main_currency not in MAIN_SYMBOLS:
            # E.g. BTC, which is no longer offered as a display currency
            user.main_currency = 'USD'
            db_sess.commit()
        return user

def create_app():
    """Creates and configures the Flask application instance."""
    # Set paths to templates and static directories located in the project root.
    import os
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register application blueprints.
    from .blueprints.auth_routes import auth_bp
    from .blueprints.portfolio_routes import portfolio_bp
    from .blueprints.market_routes import market_bp
    from .blueprints.main_routes import main_bp
    from .blueprints.api_routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    return app
