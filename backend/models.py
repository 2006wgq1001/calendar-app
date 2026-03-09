from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    bio = db.Column(db.Text)
    gender = db.Column(db.String(10))
    birthdate = db.Column(db.String(10))  # yyyy-mm-dd
    avatar = db.Column(db.Text)

    events = db.relationship('Event', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'bio': self.bio,
            'gender': self.gender,
            'birthdate': self.birthdate,
            'avatar': self.avatar,
        }


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5))  # 存储格式：HH:MM
    end_time = db.Column(db.String(5))  # 存储格式：HH:MM
    color = db.Column(db.String(20), default='#3788d8')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_user=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'description': self.description,
            'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
            'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'color': self.color
        }
        if include_user and self.user:
            # avoid circular import; assume user has to_dict
            data['user'] = self.user.to_dict()
        return data