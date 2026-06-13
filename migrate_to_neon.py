"""既存SQLite（instance/database.db）のデータを Neon Postgres へ移行する一回限りのスクリプト。

特徴:
- 依存は psycopg2 だけ（Flask等は不要）。`pip3 install psycopg2-binary` を入れれば動く。
- テーブルはRenderのビルド時に init_db.py が作成済みである前提（このスクリプトはINSERTのみ）。
- ON CONFLICT DO NOTHING なので、重複実行しても安全。
- 最後にシーケンス（自動採番）を現在の最大IDに合わせて、以後の新規登録がID衝突しないようにする。

使い方（あなたのMacで）:
    pip3 install psycopg2-binary
    # PythonAnywhereからダウンロードした database.db を instance/ に置いておく
    DATABASE_URL='postgresql://ユーザー:パスワード@ホスト/DB名?sslmode=require' python3 migrate_to_neon.py
"""
import os
import sys
import sqlite3
from datetime import date, datetime

import psycopg2

SQLITE_PATH = os.path.join('instance', 'database.db')

# (テーブル名, 列リスト, シーケンス名, 日付列の型マップ)
TABLES = [
    ('users', ['id', 'email', 'password_hash'], 'users_id_seq', {}),
    ('profiles',
     ['id', 'user_id', 'height', 'start_weight', 'target_weight', 'target_date', 'age', 'activity_level'],
     'profiles_id_seq', {'target_date': 'date'}),
    ('weight_logs', ['id', 'user_id', 'date', 'weight'], 'weight_logs_id_seq', {'date': 'date'}),
    ('calorie_logs', ['id', 'user_id', 'date', 'type', 'name', 'calories'], 'calorie_logs_id_seq', {'date': 'date'}),
    ('invite_codes',
     ['id', 'code', 'created_by', 'used_by', 'used_at', 'created_at'],
     'invite_codes_id_seq', {'used_at': 'datetime', 'created_at': 'datetime'}),
]


def parse_date(v):
    if v is None or v == '':
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    return date.fromisoformat(str(v)[:10])


def parse_datetime(v):
    if v is None or v == '':
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).replace('/', '-')
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.fromisoformat(s[:19])


def get_database_url():
    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DATABASE_URL')
    if not url:
        print("❌ DATABASE_URL を指定してください（引数 or 環境変数）")
        sys.exit(1)
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def sqlite_tables(cur):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {r[0] for r in cur.fetchall()}


def main():
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLiteファイルが見つかりません: {SQLITE_PATH}")
        print("   PythonAnywhereの Files タブから database.db をダウンロードし、instance/ に置いてください。")
        sys.exit(1)

    pg_url = get_database_url()

    slite = sqlite3.connect(SQLITE_PATH)
    slite.row_factory = sqlite3.Row
    scur = slite.cursor()
    existing = sqlite_tables(scur)

    pg = psycopg2.connect(pg_url)
    pcur = pg.cursor()

    summary = {}
    for table, cols, seq, datemap in TABLES:
        if table not in existing:
            continue
        scur.execute(f"SELECT * FROM {table}")
        rows = scur.fetchall()
        n = 0
        for row in rows:
            values = []
            for c in cols:
                v = row[c] if c in row.keys() else None
                kind = datemap.get(c)
                if kind == 'date':
                    v = parse_date(v)
                elif kind == 'datetime':
                    v = parse_datetime(v)
                values.append(v)
            placeholders = ', '.join(['%s'] * len(cols))
            collist = ', '.join(cols)
            pcur.execute(
                f"INSERT INTO {table} ({collist}) VALUES ({placeholders}) "
                f"ON CONFLICT (id) DO NOTHING",
                values,
            )
            n += 1
        # シーケンスを最大IDに合わせる（次の新規採番がぶつからないように）
        pcur.execute(
            f"SELECT setval('{seq}', COALESCE((SELECT MAX(id) FROM {table}), 1), true)"
        )
        summary[table] = n

    pg.commit()
    pcur.close()
    pg.close()
    slite.close()

    print("✅ 移行完了:")
    for t, n in summary.items():
        print(f"   {t}: {n} 件")


if __name__ == '__main__':
    main()
