import inspect
import os
from datetime import datetime
from pathlib import Path

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.attributes import flag_modified

from . import server, locks, objs
from .constants import problem_path, contest_path, submission_path
from .objs import ContestData, ProblemInfo, SubmissionData, SubmissionResult

datafile = Path.cwd() / "data" / "data.sqlite"
sqlite_url = 'sqlite:///' + str(datafile)
app = server.app
if all(k in os.environ for k in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST")):
    DB = os.environ["POSTGRES_DB"]
    USER = os.environ["POSTGRES_USER"]
    PASSWORD = os.environ["POSTGRES_PASSWORD"]
    HOST = os.environ["POSTGRES_HOST"]
    postgres_url = f"postgresql://{USER}:{PASSWORD}@{HOST}/{DB}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url
else:
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_url
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
    api_key = db.Column(db.String(64), nullable=True)

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

    @property
    def datas(self) -> SubmissionData:
        dat = self.data or {}
        return SubmissionData(**dat)

    @datas.setter
    def datas(self, value: SubmissionData):
        self.data = objs.as_dict(value)
        flag_modified(self, "data")

    @property
    def results(self) -> SubmissionResult:
        res = self.result or {}
        return SubmissionResult(**res)

    @results.setter
    def results(self, value: SubmissionResult):
        self.result = objs.as_dict(value)
        flag_modified(self, "result")


def Problem_compatibility_layer(dat):
    keys = inspect.signature(ProblemInfo).parameters.keys()
    my_keys = list(dat.keys())
    for k in my_keys:
        if k not in keys:
            dat.pop(k)
    for k in ("testcases", "testcases_gen"):
        o = dat.get(k, [])
        for v in o:
            if "in" in v:
                v["in_file"] = v.pop("in")
            if "out" in v:
                v["out_file"] = v.pop("out")
    if "score" in dat.get("statement", {}):
        dat["statement"].pop("score")
    return dat


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
        return (self.datas.languages.get(lang, True) and
                (not self.datas.runner_enabled or lang in self.datas.runner_source.keys()))

    @property
    def path(self) -> Path:
        """
        returns the path to the problem
        :return: problem_path / pid
        """
        return problem_path / self.pid

    @property
    def datas(self) -> ProblemInfo:
        return ProblemInfo(**self.data)

    @datas.setter
    def datas(self, value: ProblemInfo):
        self.data = objs.as_dict(value)
        flag_modified(self, "data")

    @property
    def new_datas(self) -> ProblemInfo:
        return ProblemInfo(**self.new_data)

    @new_datas.setter
    def new_datas(self, value: ProblemInfo):
        self.new_data = objs.as_dict(value)
        flag_modified(self, "new_data")


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
        return (self.datas.practice == "public") and per and per.is_over()

    @property
    def path(self) -> Path:
        """
        returns the path to the contest
        :return: contest_path / cid
        """
        return contest_path / self.cid

    @property
    def datas(self) -> ContestData:
        return ContestData(**self.data)

    @datas.setter
    def datas(self, value: ContestData):
        self.data = objs.as_dict(value)
        flag_modified(self, "data")


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
    # compatibility resolution
    need_compatibility_resolution = False
    if need_compatibility_resolution:
        for problem in Problem.query.all():
            problem: Problem
            dat = problem.data
            dat = objs.as_dict(objs.ProblemInfo(**Problem_compatibility_layer(dat)))
            problem.data = dat
            flag_modified(problem, "data")
            if problem.new_data is not None:
                dat = problem.new_data
                dat = objs.as_dict(objs.ProblemInfo(**Problem_compatibility_layer(dat)))
            problem.new_data = dat
            flag_modified(problem, "new_data")
            db.session.add(problem)
        db.session.commit()


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
