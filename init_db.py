"""テーブルを作成・確認する一回限りのスクリプト。

新しいテーブルを追加したとき、または初回セットアップのときだけ手動で実行する:

    python3 init_db.py

通常のWebワーカー起動では db.create_all() を行わない（app.py参照）。
PythonAnywhereのNFS上でSQLiteのスキーマロックがデッドロックし、
サイト全体が固まる事故を防ぐため。

※実行する際は、できればWebアプリをReloadで止めた直後など、
  他からDBへの書き込みが走っていないタイミングが安全。
"""
from app import app
from models import db


def main():
    with app.app_context():
        db.create_all()
        print("✅ テーブルを作成・確認しました")


if __name__ == '__main__':
    main()
