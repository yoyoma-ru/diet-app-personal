import os
from flask import Flask, send_from_directory
from dotenv import load_dotenv
from models import db
from auth import auth_bp, login_manager
from api import api_bp

load_dotenv()


def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # DATABASE_URL があればそれを使う（本番=PythonAnywhereのMySQL）。
    # 無ければローカル開発用にSQLiteへフォールバックする。
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # MySQL（PythonAnywhere）。
        # PythonAnywhereは約5分でアイドル接続を切るため、pool_recycleで先回りして張り直す。
        # これをしないと "MySQL server has gone away" エラーになる。
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_recycle': 280,
            'pool_pre_ping': True,
        }
    else:
        # ローカル開発用 SQLite
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'check_same_thread': False, 'timeout': 10},
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

    # 注意: ここでは db.create_all() を呼ばない。
    # PythonAnywhereのNFS上では、Webワーカー起動のたびにスキーマロックを取りに行くと
    # SQLiteがデッドロックし、database.db-journal が残ってサイト全体が固まる。
    # テーブル作成が必要なとき（新テーブル追加・初回構築）だけ `python3 init_db.py` を手動実行する。

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
