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
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # SQLiteのロック待ちは10秒で打ち切る。長すぎるとワーカーが固まり全体が遅くなるため。
    # 同時書き込みはAPI側の一括エンドポイントで1トランザクションに集約し、競合自体を減らす。
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {
            'check_same_thread': False,
            'timeout': 10,
        },
        'pool_recycle': 280,
        'pool_pre_ping': True,
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
