from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import date

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    profile = db.relationship('Profile', backref='user', uselist=False, cascade='all, delete-orphan')
    weight_logs = db.relationship('WeightLog', backref='user', cascade='all, delete-orphan')
    calorie_logs = db.relationship('CalorieLog', backref='user', cascade='all, delete-orphan')


class Profile(db.Model):
    __tablename__ = 'profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    height = db.Column(db.Integer, default=175)
    start_weight = db.Column(db.Float, default=60.0)
    target_weight = db.Column(db.Float, default=54.0)
    target_date = db.Column(db.Date, default=lambda: date(2026, 8, 11))
    age = db.Column(db.Integer, default=25)
    activity_level = db.Column(db.String(20), default='sedentary')


class WeightLog(db.Model):
    __tablename__ = 'weight_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    weight = db.Column(db.Float, nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='uq_user_date'),)


class CalorieLog(db.Model):
    __tablename__ = 'calorie_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'meal' or 'exercise'
    name = db.Column(db.String(255), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
