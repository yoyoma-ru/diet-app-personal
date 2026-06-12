import os
import sqlite3
from flask import Flask, send_from_directory
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
from models import db
from auth import auth_bp, login_manager
from api import api_bp

load_dotenv()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, conn_record):
    """SQLite接続のたびにPRAGMAを設定する。MySQL等では何もしない。
    - busy_timeout: ロック待ちを5秒で打ち切り、ワーカーが長時間固まるのを防ぐ
    - synchronous=NORMAL: 書き込みを速くし、中断される時間窓を小さくする
    """
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


def _heal_stale_sqlite_journal(db_path):
    """起動時、残骸ジャーナル(database.db-journal)があればSQLite正規の復旧を試みる。

    Webワーカー起動のたびに単一スレッドで実行する。接続を開いて軽い読み取りを行うと、
    SQLiteが中断トランザクションを自動でロールバックし、ジャーナルを削除する（データ破損なし）。
    これにより、書き込み中断で残ったジャーナルが次の起動で自動掃除され、
    手動の rm が不要になる。復旧できなければ黙ってスキップ（手動対応にフォールバック）。
    """
    journal = db_path + '-journal'
    if not os.path.exists(journal):
        return
    try:
        # integrity_check（全ページ読み取り）でSQLiteがホットジャーナルを検出し、
        # 中断トランザクションを本体DBへロールバック反映する（データ破損なし）。
        conn = sqlite3.connect(db_path, timeout=8)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        # ロールバックは本体反映済みなので、残ったジャーナルは安全に削除できる。
        # （integrity_checkだけではジャーナルファイルが残ることがあるため明示削除する）
        if os.path.exists(journal):
            os.remove(journal)
        print(f"ℹ️ 残骸ジャーナルを自動復旧しました (integrity={result[0] if result else '?'})")
    except Exception as e:
        print(f"⚠️ ジャーナル自動復旧に失敗（手動対応が必要かも）: {e}")


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
        # SQLite（本番=PythonAnywhere無料枠 / ローカル開発の両方）
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'connect_args': {'check_same_thread': False, 'timeout': 5},
        }
        # 起動時に残骸ジャーナルがあれば自動復旧する（Flaskのinstanceフォルダ基準）。
        db_file = os.path.join(app.instance_path, 'database.db')
        _heal_stale_sqlite_journal(db_file)
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
