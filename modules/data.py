import os
from flask_sqlalchemy import SQLAlchemy

from modules import server

datafile = os.path.abspath(os.path.join(os.getcwd(), "data", "data.sqlite"))
app = server.app
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + datafile
db = SQLAlchemy(app)


def init():
    db.create_all()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120), unique=True)
    password_sha256_hex = db.Column(db.String(64))
    permissions = db.Column(db.String(100))
    submissions = db.relationship('Submission', backref='user')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(20))
    time = db.Column(db.Time)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    problem_id = db.Column(db.Integer, db.ForeignKey('problems.id'))
    language_id = db.Column(db.Integer, db.ForeignKey('languages.id'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Problem(db.Model):
    __tablename__ = 'problems'
    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(120))
    data = db.Column(db.JSON)
    submissions = db.relationship('Submission', backref='problem')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Language(db.Model):
    __tablename__ = 'languages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    data = db.Column(db.JSON)
    submissions = db.relationship('Submission', backref='language')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
