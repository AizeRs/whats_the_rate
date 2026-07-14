from app import create_app
from data import db_session
from constants import HOST, PORT

app = create_app()

if __name__ == '__main__':
    db_session.global_init('db/users.db')
    try:
        app.run(port=PORT, host=HOST)
    except OSError:
        app.run(port=8080, host='localhost')
