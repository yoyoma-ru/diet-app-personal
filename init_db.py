"""テーブルを作成・確認するスクリプト。

接続先（app.py参照）に対して db.create_all() を実行する。
- Render(本番): render.yaml の buildCommand から呼ばれ、Neon Postgres上にテーブルを作る。
- ローカル/その他: 手動で `python3 init_db.py` を実行すれば、その接続先にテーブルを作る。

通常のWebワーカー起動時には呼ばない（app.py参照）。SQLite運用時に起動毎の
スキーマロックでデッドロックする事故を避ける名残だが、Postgresでも起動を軽くするため踏襲。
"""
from app import app
from models import db


def main():
    with app.app_context():
        db.create_all()
        print("✅ テーブルを作成・確認しました")


if __name__ == '__main__':
    main()
