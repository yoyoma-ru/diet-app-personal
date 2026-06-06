from flask import Blueprint, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import bcrypt
from datetime import date, datetime
from models import db, User, Profile, InviteCode

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
    data = request.get_json()
    email = data.get('email', '').lower().strip()
    password = data.get('password', '')
    invite_code_str = data.get('invite_code', '').strip().upper()

    # バリデーション
    if not email or not password:
        return jsonify({'error': 'メールアドレスとパスワードを入力してください'}), 400
    if len(password) < 8:
        return jsonify({'error': 'パスワードは8文字以上にしてください'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'このメールアドレスはすでに使用されています'}), 400

    # 2人目以降は招待コードが必須
    is_first_user = User.query.count() == 0
    invite = None
    if not is_first_user:
        if not invite_code_str:
            return jsonify({'error': '招待コードを入力してください'}), 400
        invite = InviteCode.query.filter_by(code=invite_code_str).first()
        if not invite or invite.used_by is not None:
            return jsonify({'error': '招待コードが無効または使用済みです'}), 403

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

    # 招待コードを使用済みにする
    if invite:
        invite.used_by = user.id
        invite.used_at = datetime.utcnow()

    db.session.commit()

    login_user(user, remember=True)
    return jsonify({'message': 'アカウントを作成しました'}), 201
