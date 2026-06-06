from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import date, timedelta, datetime, timezone
import secrets
import string
from models import db, Profile, WeightLog, CalorieLog, InviteCode

api_bp = Blueprint('api', __name__)

JST = timezone(timedelta(hours=9))

def today_jst():
    """日本時間（UTC+9）の今日の日付を返す"""
    return datetime.now(JST).date()

ACTIVITY_FACTORS = {
    'sedentary': 1.2,
    'light': 1.375,
    'moderate': 1.55,
    'active': 1.725,
    'very_active': 1.9,
}


def _calc_nutrition(profile, current_weight):
    bmr = 10 * current_weight + 6.25 * profile.height - 5 * profile.age + 5
    tdee = bmr * ACTIVITY_FACTORS.get(profile.activity_level, 1.2)
    days_remaining = max(1, (profile.target_date - today_jst()).days)
    weight_to_lose = max(0.0, current_weight - profile.target_weight)
    required_deficit = weight_to_lose * 7700 / days_remaining
    recommended = max(1200, tdee - required_deficit)
    return {
        'bmr': round(bmr),
        'tdee': round(tdee),
        'required_deficit': round(required_deficit),
        'recommended_intake': round(recommended),
    }


def _latest_weight(user_id):
    log = WeightLog.query.filter_by(user_id=user_id).order_by(WeightLog.date.desc()).first()
    return log.weight if log else None


# ── プロフィール ──────────────────────────────────────────────────────────────

@api_bp.route('/api/profile')
@login_required
def get_profile():
    p = current_user.profile
    return jsonify({
        'height': p.height,
        'start_weight': p.start_weight,
        'target_weight': p.target_weight,
        'target_date': p.target_date.isoformat(),
        'age': p.age,
        'activity_level': p.activity_level,
    })


@api_bp.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    p = current_user.profile
    d = request.get_json()
    if 'height' in d:
        p.height = int(d['height'])
    if 'start_weight' in d:
        p.start_weight = float(d['start_weight'])
    if 'target_weight' in d:
        p.target_weight = float(d['target_weight'])
    if 'target_date' in d:
        p.target_date = date.fromisoformat(d['target_date'])
    if 'age' in d:
        p.age = int(d['age'])
    if 'activity_level' in d:
        p.activity_level = d['activity_level']
    db.session.commit()
    return jsonify({'message': 'プロフィールを更新しました'})


# ── 体重記録 ──────────────────────────────────────────────────────────────────

@api_bp.route('/api/weight')
@login_required
def get_weight():
    logs = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.date).all()
    return jsonify([{'id': l.id, 'date': l.date.isoformat(), 'weight': l.weight} for l in logs])


@api_bp.route('/api/weight', methods=['POST'])
@login_required
def add_weight():
    d = request.get_json()
    log_date = date.fromisoformat(d.get('date', today_jst().isoformat()))
    weight = float(d['weight'])

    existing = WeightLog.query.filter_by(user_id=current_user.id, date=log_date).first()
    if existing:
        existing.weight = weight
        db.session.commit()
        return jsonify({'id': existing.id, 'date': log_date.isoformat(), 'weight': weight})

    log = WeightLog(user_id=current_user.id, date=log_date, weight=weight)
    db.session.add(log)
    db.session.commit()
    return jsonify({'id': log.id, 'date': log_date.isoformat(), 'weight': weight}), 201


@api_bp.route('/api/weight/<int:log_id>', methods=['DELETE'])
@login_required
def delete_weight(log_id):
    log = WeightLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    return jsonify({'message': '削除しました'})


# ── カロリー記録 ──────────────────────────────────────────────────────────────

@api_bp.route('/api/calories/<string:log_date>')
@login_required
def get_calories(log_date):
    d = date.fromisoformat(log_date)
    logs = CalorieLog.query.filter_by(user_id=current_user.id, date=d).all()

    meals = [{'id': l.id, 'name': l.name, 'calories': l.calories} for l in logs if l.type == 'meal']
    exercises = [{'id': l.id, 'name': l.name, 'calories': l.calories} for l in logs if l.type == 'exercise']

    total_intake = sum(i['calories'] for i in meals)
    total_burned = sum(i['calories'] for i in exercises)

    today_log = WeightLog.query.filter_by(user_id=current_user.id, date=d).first()
    current_weight = today_log.weight if today_log else (_latest_weight(current_user.id) or current_user.profile.start_weight)
    nutrition = _calc_nutrition(current_user.profile, current_weight)

    return jsonify({
        'meals': meals,
        'exercises': exercises,
        'total_intake': total_intake,
        'total_burned': total_burned,
        'net_calories': total_intake - total_burned,
        'recommended_intake': nutrition['recommended_intake'],
        'remaining': nutrition['recommended_intake'] - total_intake + total_burned,
        'bmr': nutrition['bmr'],
        'tdee': nutrition['tdee'],
        'current_weight': current_weight,
    })


@api_bp.route('/api/calories', methods=['POST'])
@login_required
def add_calorie():
    d = request.get_json()
    log = CalorieLog(
        user_id=current_user.id,
        date=date.fromisoformat(d.get('date', today_jst().isoformat())),
        type=d['type'],
        name=d['name'],
        calories=int(d['calories']),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'id': log.id}), 201


@api_bp.route('/api/calories/<int:log_id>', methods=['PUT'])
@login_required
def update_calorie(log_id):
    log = CalorieLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    d = request.get_json()
    if 'name' in d:
        log.name = d['name']
    if 'calories' in d:
        log.calories = int(d['calories'])
    db.session.commit()
    return jsonify({'id': log.id, 'name': log.name, 'calories': log.calories})


@api_bp.route('/api/calories/<int:log_id>', methods=['DELETE'])
@login_required
def delete_calorie(log_id):
    log = CalorieLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    db.session.delete(log)
    db.session.commit()
    return jsonify({'message': '削除しました'})


# ── ダッシュボード ────────────────────────────────────────────────────────────

@api_bp.route('/api/dashboard')
@login_required
def get_dashboard():
    today = today_jst()
    profile = current_user.profile

    today_log = WeightLog.query.filter_by(user_id=current_user.id, date=today).first()
    latest_log = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.date.desc()).first()
    current_weight = latest_log.weight if latest_log else profile.start_weight

    days_remaining = max(0, (profile.target_date - today).days)
    weight_remaining = round(current_weight - profile.target_weight, 1)

    required_pace = (weight_remaining / days_remaining * 7) if days_remaining > 0 else 0

    week_ago = today - timedelta(days=7)
    old_log = WeightLog.query.filter(
        WeightLog.user_id == current_user.id,
        WeightLog.date >= week_ago,
    ).order_by(WeightLog.date).first()

    actual_pace = 0.0
    if old_log and latest_log and old_log.id != latest_log.id:
        diff_days = (latest_log.date - old_log.date).days
        if diff_days > 0:
            actual_pace = (old_log.weight - latest_log.weight) / diff_days * 7

    if actual_pace == 0:
        pace_status = 'no_data'
    elif actual_pace >= required_pace:
        pace_status = 'on_track'
    elif actual_pace >= required_pace * 0.7:
        pace_status = 'slightly_behind'
    else:
        pace_status = 'behind'

    today_calories = CalorieLog.query.filter_by(user_id=current_user.id, date=today).all()
    total_intake = sum(l.calories for l in today_calories if l.type == 'meal')
    total_burned = sum(l.calories for l in today_calories if l.type == 'exercise')

    nutrition = _calc_nutrition(profile, current_weight)

    return jsonify({
        'today_weight': today_log.weight if today_log else None,
        'current_weight': current_weight,
        'target_weight': profile.target_weight,
        'weight_remaining': weight_remaining,
        'days_remaining': days_remaining,
        'target_date': profile.target_date.isoformat(),
        'required_pace_per_week': round(required_pace, 2),
        'actual_pace_per_week': round(actual_pace, 2),
        'pace_status': pace_status,
        'calorie_intake': total_intake,
        'calorie_burned': total_burned,
        'calorie_remaining': nutrition['recommended_intake'] - total_intake + total_burned,
        'recommended_intake': nutrition['recommended_intake'],
    })


# ── 予測・分析 ────────────────────────────────────────────────────────────────

@api_bp.route('/api/analysis')
@login_required
def get_analysis():
    profile = current_user.profile
    logs = WeightLog.query.filter_by(user_id=current_user.id).order_by(WeightLog.date).all()

    if len(logs) < 2:
        return jsonify({'has_data': False, 'error': '予測には2日以上の記録が必要です'})

    start_date = logs[0].date
    x = [(l.date - start_date).days for l in logs]
    y = [l.weight for l in logs]
    n = len(x)
    sx = sum(x)
    sy = sum(y)
    sxy = sum(xi * yi for xi, yi in zip(x, y))
    sx2 = sum(xi ** 2 for xi in x)
    denom = n * sx2 - sx ** 2

    if denom == 0:
        return jsonify({'has_data': False, 'error': '計算できません（全て同じ日付）'})

    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n

    predicted_goal_date = None
    if slope < 0:
        days_to_target = (profile.target_weight - intercept) / slope
        predicted_goal_date = (start_date + timedelta(days=round(days_to_target))).isoformat()

    target_days = (profile.target_date - start_date).days
    predicted_at_target = intercept + slope * target_days
    today = today_jst()
    current_weight = logs[-1].weight
    nutrition = _calc_nutrition(profile, current_weight)

    return jsonify({
        'has_data': True,
        'slope_per_week': round(slope * 7, 2),
        'predicted_goal_date': predicted_goal_date,
        'target_date': profile.target_date.isoformat(),
        'predicted_weight_at_target': round(predicted_at_target, 1),
        'will_reach_goal': predicted_at_target <= profile.target_weight,
        'days_remaining': max(0, (profile.target_date - today).days),
        'bmr': nutrition['bmr'],
        'tdee': nutrition['tdee'],
        'required_deficit': nutrition['required_deficit'],
        'recommended_intake': nutrition['recommended_intake'],
        'data_points': n,
    })


# ── 日別履歴 ──────────────────────────────────────────────────────────────────

@api_bp.route('/api/history')
@login_required
def get_history():
    from collections import defaultdict
    sixty_ago = today_jst() - timedelta(days=60)
    logs = CalorieLog.query.filter(
        CalorieLog.user_id == current_user.id,
        CalorieLog.date >= sixty_ago,
    ).order_by(CalorieLog.date.desc()).all()

    by_date = defaultdict(lambda: {'meals': [], 'exercises': []})
    for log in logs:
        d = log.date.isoformat()
        entry = {'id': log.id, 'name': log.name, 'calories': log.calories}
        if log.type == 'meal':
            by_date[d]['meals'].append(entry)
        else:
            by_date[d]['exercises'].append(entry)

    result = []
    for d, data in sorted(by_date.items(), reverse=True):
        result.append({
            'date': d,
            'meals': data['meals'],
            'exercises': data['exercises'],
            'total_intake': sum(m['calories'] for m in data['meals']),
            'total_burned': sum(e['calories'] for e in data['exercises']),
        })

    return jsonify(result)


# ── 招待コード管理 ────────────────────────────────────────────────────────────

def _generate_unique_code():
    """重複しない8文字の英数字コードを生成"""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        if not InviteCode.query.filter_by(code=code).first():
            return code


@api_bp.route('/api/invite-codes')
@login_required
def list_invite_codes():
    codes = InviteCode.query.filter_by(created_by=current_user.id).order_by(InviteCode.created_at.desc()).all()
    return jsonify([{
        'id': c.id,
        'code': c.code,
        'used': c.used_by is not None,
        'used_at': c.used_at.isoformat() if c.used_at else None,
        'created_at': c.created_at.isoformat(),
    } for c in codes])


@api_bp.route('/api/invite-codes', methods=['POST'])
@login_required
def create_invite_code():
    code = _generate_unique_code()
    inv = InviteCode(
        code=code,
        created_by=current_user.id,
        created_at=datetime.now(JST),
    )
    db.session.add(inv)
    db.session.commit()
    return jsonify({'id': inv.id, 'code': code}), 201


@api_bp.route('/api/invite-codes/<int:code_id>', methods=['DELETE'])
@login_required
def delete_invite_code(code_id):
    inv = InviteCode.query.filter_by(id=code_id, created_by=current_user.id).first_or_404()
    if inv.used_by is not None:
        return jsonify({'error': '使用済みのコードは削除できません'}), 400
    db.session.delete(inv)
    db.session.commit()
    return jsonify({'message': '削除しました'})
