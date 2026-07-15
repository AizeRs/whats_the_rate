from app import create_app
from app.models import db_session
from app.constants import HOST, PORT

app = create_app()

if __name__ == '__main__':
    db_session.global_init('data/users.db')
    from app.services.symbols import load_main_symbols
    load_main_symbols()
    try:
        app.run(port=PORT, host=HOST)
    except OSError:
        app.run(port=8080, host='localhost')
