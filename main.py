"""
Main application entry point.
Initializes the database, loads symbols, and starts the Flask server.
"""
from app import create_app
from app.models import db_session
from app.constants import HOST, PORT

app = create_app()

if __name__ == '__main__':
    db_session.global_init('data/whats_the_rate.db')
    from app.services.symbols import load_main_symbols
    load_main_symbols()
    try:
        app.run(port=PORT, host=HOST, debug=True)
    except OSError:
        app.run(port=8080, host='localhost', debug=True)
