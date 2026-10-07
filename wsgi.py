from app import create_app
from app.models import db_session

app = create_app()
db_session.global_init('data/whats_the_rate.db')

from app.services.symbols import load_main_symbols
load_main_symbols()