from datetime import datetime
from pathlib import Path

from flask_sqlalchemy import SQLAlchemy

from . import server, locks
from .constants import problem_path, contest_path, submission_path

datafile = Path.cwd() / "data" / "data.sqlite"
app = server.app
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + str(datafile)
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True)
    display_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_sha256_hex = db.Column(db.String(64), nullable=False)
    permissions = db.Column(db.String(100), default="")
    owner_id = db.Column(db.Integer, nullable=True)
    submissions = db.relationship('Submission', backref='user', lazy='dynamic')
    problems = db.relationship('Problem', backref='user', lazy='dynamic')
    contests = db.relationship('Contest', backref='user', lazy='dynamic')
    announcements = db.relationship('Announcement', backref='user', lazy='dynamic')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def permission_list(self) -> list[str]:
        return self.permissions.split(";")


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source = db.Column(db.String(20), nullable=False)
    time = db.Column(db.DateTime, nullable=False)
    result = db.Column(db.JSON, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    problem_id = db.Column(db.Integer, db.ForeignKey('problems.id'), nullable=False)
    contest_id = db.Column(db.Integer, db.ForeignKey('contests.id'), nullable=True)
    period_id = db.Column(db.Integer, db.ForeignKey('periods.id'), nullable=True)
    language = db.Column(db.String(20), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    running = db.Column(db.Boolean, default=False)
    ce_msg = db.Column(db.Text, nullable=True)
    data = db.Column(db.JSON)
    pid = db.Column(db.String(20), nullable=False)
    just_pretest = db.Column(db.Boolean, default=False)
    simple_result = db.Column(db.String(40), nullable=True)
    queue_position = db.Column(db.Integer, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def path(self) -> Path:
        """
        returns the path to the submission
        :return: submission_path / submission_id
        """
        return submission_path / str(self.id)


class Problem(db.Model):
    __tablename__ = 'problems'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pid = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(120), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    new_data = db.Column(db.JSON, nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    submissions = db.relationship('Submission', backref='problem', lazy='dynamic')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    editing = db.Column(db.Boolean, default=False)
    edit_time = db.Column(db.DateTime)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def lang_allowed(self, lang: str) -> bool:
        return (self.data.get("languages", {}).get(lang, True) and
                (not self.data.get("runner_enabled", False) or lang in self.data.get("runner_source", {})))

    @property
    def path(self) -> Path:
        """
        returns the path to the problem
        :return: problem_path / pid
        """
        return problem_path / self.pid


class Contest(db.Model):
    __tablename__ = 'contests'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cid = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    submissions = db.relationship('Submission', backref='contest', lazy='dynamic')
    periods = db.relationship('Period', backref='contest', lazy='dynamic')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    main_period_id = db.Column(db.Integer, nullable=True)
    announcements = db.relationship('Announcement', backref='contest', lazy='dynamic')

    def can_virtual(self) -> bool:
        if not self.main_period_id:
            return False
        per: Period = Period.query.get(self.main_period_id)
        return (self.data["practice"] == "public") and per and per.is_over()

    @property
    def path(self) -> Path:
        """
        returns the path to the contest
        :return: contest_path / cid
        """
        return contest_path / self.cid


class Period(db.Model):
    __tablename__ = 'periods'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    running = db.Column(db.Boolean, default=False)
    ended = db.Column(db.Boolean, default=False)
    is_virtual = db.Column(db.Boolean, default=False)
    judging = db.Column(db.Boolean, default=False)
    contest_id = db.Column(db.Integer, db.ForeignKey('contests.id'), nullable=False)
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


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    time = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String(80), nullable=False)
    content = db.Column(db.String(1000), nullable=False)
    reply = db.Column(db.String(1000), nullable=True)
    reply_name = db.Column(db.String(80), nullable=True)
    contest_id = db.Column(db.Integer, db.ForeignKey('contests.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    public = db.Column(db.Boolean, default=True, nullable=False)
    question = db.Column(db.Boolean, default=False, nullable=False)


def init():
    db.create_all()
    if Problem.query.filter_by(pid="test").count() == 0:
        test_problem = Problem(pid="test", name="", data={}, new_data={}, user_id=1)
        add(test_problem)


lock_counter = locks.Counter()


def add(*objs):
    for obj in objs:
        db.session.add(obj)
    if not lock_counter:
        db.session.commit()


def delete(*objs):
    for obj in objs:
        db.session.delete(obj)
    if not lock_counter:
        db.session.commit()


class DelayCommit:
    def __init__(self):
        pass

    def __enter__(self):
        lock_counter.inc()

    def __exit__(self, exc_type, exc_val, exc_tb):
        cnt = lock_counter.dec()
        if cnt == 0:
            db.session.commit()
