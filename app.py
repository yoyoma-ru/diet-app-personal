import os
import time
from flask import Flask, send_from_directory
from dotenv import load_dotenv
from models import db
from auth import auth_bp, login_manager
from api import api_bp

load_dotenv()


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    # SQLiteのロックタイムアウトを30秒に設定（PythonAnywhereのNFSロック対策）
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db?timeout=30'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30,
        }
    }
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = False

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    @app.route('/')
    def index():
        return send_from_directory('static', 'index.html')

    with app.app_context():
        for attempt in range(3):
            try:
                db.create_all()
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
