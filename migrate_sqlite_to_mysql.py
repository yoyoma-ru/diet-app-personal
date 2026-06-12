"""既存SQLite（instance/database.db）のデータを、現在appが接続しているDB（MySQL）へ移行する。

使い方（PythonAnywhereのBashで、MySQL接続済み＝DATABASE_URL設定済みの状態で）:

    cd ~/diet-app-personal
    python3 migrate_sqlite_to_mysql.py

- SQLiteは raw sqlite3 で直接読む（appの接続先がMySQLになっていてもOK）。
- MySQL側へは models 経由で書き込む。IDを保持し、merge で重複実行しても安全。
- 外部キーの順序（User → Profile → ログ類）でコミットする。
"""
import os
import sqlite3
from datetime import date, datetime

from app import app
from models import db, User, Profile, WeightLog, CalorieLog, InviteCode

SQLITE_PATH = os.path.join('instance', 'database.db')


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
    s = str(v)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # 'YYYY-MM-DD HH:MM:SS' などの揺れに対応
        return datetime.fromisoformat(s.replace('/', '-'))


def table_columns(cur, table):
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]


def main():
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLiteファイルが見つかりません: {SQLITE_PATH}")
        return

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # SQLiteに存在するテーブルだけを対象にする
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {r[0] for r in cur.fetchall()}

    with app.app_context():
        db.create_all()  # MySQL側にテーブルを作成

        counts = {}

        # 1) users
        if 'users' in existing:
            n = 0
            for row in cur.execute("SELECT * FROM users"):
                db.session.merge(User(
                    id=row['id'], email=row['email'], password_hash=row['password_hash'],
                ))
                n += 1
            db.session.commit()
            counts['users'] = n

        # 2) profiles
        if 'profiles' in existing:
            n = 0
            for row in cur.execute("SELECT * FROM profiles"):
                db.session.merge(Profile(
                    id=row['id'], user_id=row['user_id'], height=row['height'],
                    start_weight=row['start_weight'], target_weight=row['target_weight'],
                    target_date=parse_date(row['target_date']), age=row['age'],
                    activity_level=row['activity_level'],
                ))
                n += 1
            db.session.commit()
            counts['profiles'] = n

        # 3) weight_logs
        if 'weight_logs' in existing:
            n = 0
            for row in cur.execute("SELECT * FROM weight_logs"):
                db.session.merge(WeightLog(
                    id=row['id'], user_id=row['user_id'],
                    date=parse_date(row['date']), weight=row['weight'],
                ))
                n += 1
            db.session.commit()
            counts['weight_logs'] = n

        # 4) calorie_logs
        if 'calorie_logs' in existing:
            n = 0
            for row in cur.execute("SELECT * FROM calorie_logs"):
                db.session.merge(CalorieLog(
                    id=row['id'], user_id=row['user_id'], date=parse_date(row['date']),
                    type=row['type'], name=row['name'], calories=row['calories'],
                ))
                n += 1
            db.session.commit()
            counts['calorie_logs'] = n

        # 5) invite_codes
        if 'invite_codes' in existing:
            cols = table_columns(cur, 'invite_codes')
            n = 0
            for row in cur.execute("SELECT * FROM invite_codes"):
                db.session.merge(InviteCode(
                    id=row['id'], code=row['code'], created_by=row['created_by'],
                    used_by=row['used_by'] if 'used_by' in cols else None,
                    used_at=parse_datetime(row['used_at']) if 'used_at' in cols else None,
                    created_at=parse_datetime(row['created_at']) if 'created_at' in cols else None,
                ))
                n += 1
            db.session.commit()
            counts['invite_codes'] = n

    conn.close()

    print("✅ 移行完了:")
    for t, n in counts.items():
        print(f"   {t}: {n} 件")


if __name__ == '__main__':
    main()
