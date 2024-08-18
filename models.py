from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now())
    rep_goal = db.Column(db.Integer, nullable=True)
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Exercises(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    link = db.Column(db.String(200), unique=True, nullable=False)


class UserExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    exercise_id = db.Column(db.Integer)
    total_reps = db.Column(db.Integer, nullable=False)
    rom_score = db.Column(db.Float, nullable=False)
    tut_score = db.Column(db.Float, nullable=False)
    count = db.Column(db.Integer, nullable=True, default=0)
    date = db.Column(db.DateTime, default=datetime.datetime.now())

