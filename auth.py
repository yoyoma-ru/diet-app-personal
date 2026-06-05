from flask import Blueprint, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import bcrypt
from datetime import date
from models import db, User, Profile

auth_bp = Blueprint('auth', __name__)
login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'Unauthorized'}), 401


@auth_bp.route('/api/auth/status')
def status():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True, 'email': current_user.email})
    return jsonify({'authenticated': False})


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return jsonify({'error': 'メールアドレスまたはパスワードが正しくありません'}), 401

    login_user(user, remember=True)
    return jsonify({'message': 'ログインしました'})


@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'ログアウトしました'})


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    if User.query.count() > 0:
        return jsonify({'error': 'このアプリはすでに登録済みです'}), 403

    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'メールアドレスとパスワードを入力してください'}), 400
    if len(password) < 8:
        return jsonify({'error': 'パスワードは8文字以上にしてください'}), 400

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.flush()

    profile = Profile(
        user_id=user.id,
        height=175,
        start_weight=60.0,
        target_weight=54.0,
        target_date=date(2026, 8, 11),
        age=31,
        activity_level='sedentary',
    )
    db.session.add(profile)
    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'message': 'アカウントを作成しました'}), 201
