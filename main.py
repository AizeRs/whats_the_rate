from constants import *
import data_api_functions
from flask import Flask, render_template

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY


@app.route('/')
@app.route('/index')
def index():
    param = {}
    return render_template('index.html', **param)


if __name__ == '__main__':
    app.run(port=8080, host='127.0.0.1')
