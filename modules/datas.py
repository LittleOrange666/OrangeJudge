import os
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

from modules import server

datafile = os.path.abspath(os.path.join(os.getcwd(), "data", "data.sqlite"))
app = server.app
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + datafile
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True)
    display_name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True)
    password_sha256_hex = db.Column(db.String(64))
    permissions = db.Column(db.String(100), default="")
    is_team = db.Column(db.Boolean, default=False)
    owner_id = db.Column(db.Integer, nullable=True)
    submissions = db.relationship('Submission', backref='user', lazy='dynamic')
    problems = db.relationship('Problem', backref='user', lazy='dynamic')
    contests = db.relationship('Contest', backref='user', lazy='dynamic')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def permission_list(self) -> list[str]:
        return self.permissions.split(";")


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source = db.Column(db.String(20))
    time = db.Column(db.DateTime)
    result = db.Column(db.JSON, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    problem_id = db.Column(db.Integer, db.ForeignKey('problems.id'))
    contest_id = db.Column(db.Integer, db.ForeignKey('contests.id'), nullable=True)
    period_id = db.Column(db.Integer, db.ForeignKey('periods.id'), nullable=True)
    language = db.Column(db.String(20))
    completed = db.Column(db.Boolean, default=False)
    ce_msg = db.Column(db.Text, nullable=True)
    data = db.Column(db.JSON)
    pid = db.Column(db.String(20))
    just_pretest = db.Column(db.Boolean, default=False)
    simple_result = db.Column(db.String(40))
    queue_position = db.Column(db.Integer)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Problem(db.Model):
    __tablename__ = 'problems'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pid = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(120))
    data = db.Column(db.JSON)
    new_data = db.Column(db.JSON)
    is_public = db.Column(db.Boolean, default=False)
    submissions = db.relationship('Submission', backref='problem', lazy='dynamic')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    editing = db.Column(db.Boolean, default=False)
    edit_time = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Contest(db.Model):
    __tablename__ = 'contests'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cid = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(120))
    submissions = db.relationship('Submission', backref='contest', lazy='dynamic')
    periods = db.relationship('Period', backref='contest', lazy='dynamic')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    data = db.Column(db.JSON)
    main_period_id = db.Column(db.Integer, nullable=True)

    def can_virtual(self) -> bool:
        if not self.main_period_id:
            return False
        per: Period = Period.query.get(self.main_period_id)
        return (self.data["practice"] == "public") and per and per.is_over()


class Period(db.Model):
    __tablename__ = 'periods'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    running = db.Column(db.Boolean, default=False)
    ended = db.Column(db.Boolean, default=False)
    is_virtual = db.Column(db.Boolean, default=False)
    judging = db.Column(db.Boolean, default=False)
    contest_id = db.Column(db.Integer, db.ForeignKey('contests.id'))
    submissions = db.relationship('Submission', backref='period', lazy='dynamic')

    def is_running(self):
        now = datetime.now()
        return self.start_time <= now <= self.end_time

    def is_over(self):
        now = datetime.now()
        return now > self.end_time

    def is_started(self):
        now = datetime.now()
        return now >= self.start_time


def init():
    db.create_all()
    if Problem.query.filter_by(pid="test").count() == 0:
        test_problem = Problem(pid="test", name="", data={})
        add(test_problem)


def add(*objs):
    for obj in objs:
        db.session.add(obj)
    db.session.commit()
