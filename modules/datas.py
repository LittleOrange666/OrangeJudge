"""
OrangeJudge, a competitive programming platform

Copyright (C) 2024-2025 LittleOrange666 (orangeminecraft123@gmail.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import TypeVar, Type

from flask import has_request_context
from flask_sqlalchemy import SQLAlchemy
from flask_sqlalchemy.query import Query
from flask_sqlalchemy.session import Session
from loguru import logger
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from . import server, objs
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
    postgres_url = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}/{DB}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url
else:
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_url
db = SQLAlchemy(app)
SessionFactory: sessionmaker[Session] | None = None
_current_session: ContextVar = ContextVar("current_session", default=None)


@app.teardown_request
def teardown_request(exception=None):
    if exception:
        db.session.rollback()
    else:
        db.session.commit()


class User(db.Model):
    """
    Represents a user in the database.

    Attributes:
        id (int): The primary key for the user.
        username (str): The unique username of the user.
        display_name (str): The display name of the user.
        email (str): The unique email address of the user.
        password_sha256_hex (str): The SHA-256 hash of the user's password.
        permissions (str): A semicolon-separated list of permissions for the user.
        owner_id (int): The ID of the owner, if applicable.
        submissions (relationship): The submissions made by the user.
        problems (relationship): The problems created by the user.
        contests (relationship): The contests created by the user.
        announcements (relationship): The announcements made by the user.
        api_key (str): The API key for the user, if applicable.
    """
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
        """
        Initializes a new User instance.

        Args:
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(**kwargs)

    def permission_list(self) -> list[str]:
        """
        Returns the list of permissions for the user.

        Returns:
            list[str]: A list of permissions.
        """
        return self.permissions.split(";")


class Submission(db.Model):
    """
    Represents a submission in the database.

    Attributes:
        id (int): The primary key for the submission.
        source (str): The source of the submission.
        time (datetime): The time of the submission.
        result (dict): The result of the submission.
        user_id (int): The ID of the user who made the submission.
        problem_id (int): The ID of the problem associated with the submission.
        contest_id (int): The ID of the contest associated with the submission.
        period_id (int): The ID of the period associated with the submission.
        language (str): The programming language of the submission.
        completed (bool): Whether the submission is completed.
        running (bool): Whether the submission is currently running.
        ce_msg (str): The compilation error message, if any.
        data (dict): Additional data associated with the submission.
        pid (str): The problem identifier of the submission.
        just_pretest (bool): Whether the submission is just a pretest.
        simple_result (str): A simplified result of the submission.
        queue_position (int): The position of the submission in the queue.
    """
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
        """
        Initializes a new Submission instance.

        Args:
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(**kwargs)

    @property
    def path(self) -> Path:
        """
        Returns the path to the submission.

        Returns:
            Path: The path to the submission.
        """
        return submission_path / str(self.id)

    @property
    def datas(self) -> SubmissionData:
        """
        Returns the data associated with the submission.

        Returns:
            SubmissionData: The data associated with the submission.
        """
        dat = self.data or {}
        return SubmissionData(**dat)

    @datas.setter
    def datas(self, value: SubmissionData):
        """
        Sets the data associated with the submission.

        Args:
            value (SubmissionData): The data to set.
        """
        self.data = objs.as_dict(value)
        flag_modified(self, "data")

    @property
    def results(self) -> SubmissionResult:
        """
        Returns the results of the submission.

        Returns:
            SubmissionResult: The results of the submission.
        """
        res = self.result or {}
        return SubmissionResult(**res)

    @results.setter
    def results(self, value: SubmissionResult):
        """
        Sets the results of the submission.

        Args:
            value (SubmissionResult): The results to set.
        """
        self.result = objs.as_dict(value)
        flag_modified(self, "result")


class Problem(db.Model):
    """
    Represents a problem in the database.

    Attributes:
        id (int): The primary key for the problem.
        pid (str): The unique problem identifier.
        name (str): The name of the problem.
        data (dict): The data associated with the problem.
        new_data (dict): The modifying version of the data associated with the problem.
        is_public (bool): Whether the problem is public.
        submissions (relationship): The submissions related to the problem.
        user_id (int): The ID of the user who created the problem.
        editing (bool): Whether the problem is currently being edited.
        edit_time (datetime): The time when the problem was last edited.
    """
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
        """
        Initializes a new Problem instance.

        Args:
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(**kwargs)

    def lang_allowed(self, lang: str) -> bool:
        """
        Check if the given language is allowed for the problem.

        Args:
            lang (str): The programming language to check.

        Returns:
            bool: True if the language is allowed, False otherwise.
        """
        return (self.datas.languages.get(lang, True) and
                (not self.datas.runner_enabled or lang in self.datas.runner_source.keys()))

    @property
    def path(self) -> Path:
        """
        Get the path to the problem.

        Returns:
            Path: The path to the problem.
        """
        return problem_path / self.pid

    @property
    def datas(self) -> ProblemInfo:
        """
        Get the data associated with the problem.

        Returns:
            ProblemInfo: The data associated with the problem.
        """
        return ProblemInfo(**self.data)

    @datas.setter
    def datas(self, value: ProblemInfo):
        """
        Set the data associated with the problem.

        Args:
            value (ProblemInfo): The data to set.
        """
        self.data = objs.as_dict(value)
        flag_modified(self, "data")

    @property
    def new_datas(self) -> ProblemInfo:
        """
        Get the modifying version of the data associated with the problem.

        Returns:
            ProblemInfo: The modifying version of the data associated with the problem.
        """
        return ProblemInfo(**self.new_data)

    @new_datas.setter
    def new_datas(self, value: ProblemInfo):
        """
        Set the modifying version of the data associated with the problem.

        Args:
            value (ProblemInfo): The new data to set.
        """
        self.new_data = objs.as_dict(value)
        flag_modified(self, "new_data")


class Contest(db.Model):
    """
    Represents a contest in the database.

    Attributes:
        id (int): The primary key for the contest.
        cid (str): The unique contest identifier.
        name (str): The name of the contest.
        submissions (relationship): The submissions related to the contest.
        periods (relationship): The periods related to the contest.
        user_id (int): The ID of the user who created the contest.
        data (dict): The data associated with the contest.
        main_period_id (int): The ID of the main period, if applicable.
        announcements (relationship): The announcements related to the contest.
    """
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
        """
        Check if the contest can be virtual.

        This method checks if the contest can be virtual based on the main period and practice settings.

        Returns:
            bool: True if the contest can be virtual, False otherwise.
        """
        if not self.main_period_id:
            return False
        per: Period = get_by_id(Period, self.main_period_id)
        return (self.datas.practice == "public") and per is not None and per and per.is_over()

    @property
    def path(self) -> Path:
        """
        Get the path to the contest.

        Returns:
            Path: The path to the contest.
        """
        return contest_path / self.cid

    @property
    def datas(self) -> ContestData:
        """
        Get the data associated with the contest.

        Returns:
            ContestData: The data associated with the contest.
        """
        return ContestData(**self.data)

    @datas.setter
    def datas(self, value: ContestData):
        """
        Set the data associated with the contest.

        Args:
            value (ContestData): The data to set.
        """
        self.data = objs.as_dict(value)
        flag_modified(self, "data")


class Period(db.Model):
    """
    Represents a period in the database.

    Attributes:
        id (int): The primary key for the period.
        start_time (datetime): The start time of the period.
        end_time (datetime): The end time of the period.
        running (bool): Whether the period is currently running.
        ended (bool): Whether the period has ended.
        is_virtual (bool): Whether the period is virtual.
        judging (bool): Whether the period is in the judging phase.
        contest_id (int): The ID of the contest associated with the period.
        submissions (relationship): The submissions related to the period.
    """
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
        """
        Check if the period is currently running.

        Returns:
            bool: True if the current time is within the start and end time, False otherwise.
        """
        now = datetime.now()
        return self.start_time <= now <= self.end_time

    def is_over(self):
        """
        Check if the period is over.

        Returns:
            bool: True if the current time is after the end time, False otherwise.
        """
        now = datetime.now()
        return now > self.end_time

    def is_started(self):
        """
        Check if the period has started.

        Returns:
            bool: True if the current time is after the start time, False otherwise.
        """
        now = datetime.now()
        return now >= self.start_time


class Announcement(db.Model):
    """
    Represents an announcement in the database.

    Attributes:
        id (int): The primary key for the announcement.
        time (datetime): The time the announcement was made.
        title (str): The title of the announcement.
        content (str): The content of the announcement.
        reply (str): The reply to the announcement, if any.
        reply_name (str): The name of the person who replied, if any.
        contest_id (int): The ID of the contest associated with the announcement.
        user_id (int): The ID of the user who made the announcement.
        public (bool): Whether the announcement is public.
        question (bool): Whether the announcement is a question.
    """
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
    global SessionFactory
    db.create_all()
    SessionFactory = sessionmaker(bind=db.engine)


T = TypeVar('T')


@contextmanager
def SessionContext():
    """
    Provide a transactional scope around a series of operations.

    This context manager yields a SQLAlchemy session. If the context is within a Flask request,
    it uses the Flask session. Otherwise, it creates a new session and manages its lifecycle.

    Yields:
        SQLAlchemy session: The database session to be used within the context.

    Raises:
        Exception: If an error occurs during the session, it rolls back the transaction.
    """
    if has_request_context():
        yield db.session
    elif _current_session.get() is not None:
        yield _current_session.get()
    else:
        # logger.info("Creating new session")
        # traceback.print_stack()
        session = SessionFactory()
        token = _current_session.set(session)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            _current_session.reset(token)
        # logger.info("Session closed")


def get_session() -> Session:
    """
    Retrieve the current SQLAlchemy session.

    This function returns the current SQLAlchemy session. If the context is within a Flask request,
    it uses the Flask session. Otherwise, it retrieves the session from the context variable.
    If no session is found in a non-request context, it raises a RuntimeError.

    Returns:
        SQLAlchemy session: The current database session.

    Raises:
        RuntimeError: If no session is found in a non-request context.
    """
    if has_request_context():
        return db.session
    session = _current_session.get()
    if session is None:
        raise RuntimeError("No session found in non-request context. Use SessionContext.")
    return session


def add(*objs):
    """
    Add the given objects to the database session.

    This function retrieves the current SQLAlchemy session and adds the provided objects to it.

    Args:
        *objs: Variable length argument list of objects to add to the database session.
    """
    session = get_session()
    for obj in objs:
        session.add(obj)


def delete(*objs):
    """
    Delete the given objects from the database session.

    This function retrieves the current SQLAlchemy session and deletes the provided objects from it.

    Args:
        *objs: Variable length argument list of objects to delete from the database session.
    """
    session = get_session()
    for obj in objs:
        session.delete(obj)


def flush():
    """
    Flush the current SQLAlchemy session.

    This function retrieves the current SQLAlchemy session and flushes it, sending all pending changes to the database.
    """
    session = get_session()
    session.flush()


def query(model_class: Type[T]) -> Query[T]:
    """
    Query the database for the given model class.

    This function retrieves the current SQLAlchemy session and returns a query object for the specified model class.

    Args:
        model_class (Type[T]): The model class to query.

    Returns:
        Query[T]: A query object for the specified model class.
    """
    session = get_session()
    return session.query(model_class)


def get_by_id(model_class: Type[T], _id: int) -> T | None:
    """
    Retrieve an object by its ID.

    This function retrieves the current SQLAlchemy session and returns the object of the specified model class with the given ID.

    Args:
        model_class (Type[T]): The model class of the object to retrieve.
        _id (int): The ID of the object to retrieve.

    Returns:
        T | None: The object of the specified model class with the given ID, or None if not found.
    """
    session = get_session()
    return session.get(model_class, _id)


def get_or_404(model_class: Type[T], _id: int) -> T:
    """
    Retrieve an object by its ID or raise a 404 error.

    This function retrieves the current SQLAlchemy session and returns the object of the specified model class with the given ID.
    If no match is found, it raises a 404 error.

    Args:
        model_class (Type[T]): The model class of the object to retrieve.
        _id (int): The ID of the object to retrieve.

    Returns:
        T: The object of the specified model class with the given ID.

    Raises:
        RuntimeError: If not in a request context.
    """
    if not has_request_context():
        raise RuntimeError("get_or_404 can only be used in a request context.")
    return db.get_or_404(model_class, _id)


def do_filter(model_class: Type[T], *args) -> Query[T]:
    """
    Filter the database query by the given criteria.

    This function retrieves the current SQLAlchemy session and returns a query object for the specified model class,
    filtered by the provided criteria.

    Args:
        model_class (Type[T]): The model class to query.
        *args: Positional arguments for filtering the query.

    Returns:
        Query[T]: A query object for the specified model class, filtered by the provided criteria.
    """
    session = get_session()
    return session.query(model_class).filter(*args)


def filter_by(model_class: Type[T], **kwargs) -> Query[T]:
    """
    Filter the database query by the given criteria.

    This function retrieves the current SQLAlchemy session and returns a query object for the specified model class,
    filtered by the provided criteria.

    Args:
        model_class (Type[T]): The model class to query.
        **kwargs: Keyword arguments for filtering the query.

    Returns:
        Query[T]: A query object for the specified model class, filtered by the provided criteria.
    """
    session = get_session()
    return session.query(model_class).filter_by(**kwargs)


def get_all(model_class: Type[T], **kwargs) -> list[T]:
    session = get_session()
    return session.query(model_class).filter_by(**kwargs).all()


def count(model_class: Type[T], **kwargs) -> int:
    """
    Count the number of records in the database for the given model class.

    This function retrieves the current SQLAlchemy session and returns the count of records
    for the specified model class, filtered by the provided criteria.

    Args:
        model_class (Type[T]): The model class to query.
        **kwargs: Keyword arguments for filtering the query.

    Returns:
        int: The count of records that match the given criteria.
    """
    session = get_session()
    return session.query(model_class).filter_by(**kwargs).count()


def first(model_class: Type[T], **kwargs) -> T | None:
    """
    Retrieve the first record that matches the given criteria.

    This function retrieves the current SQLAlchemy session and returns the first record
    of the specified model class that matches the provided criteria.

    Args:
        model_class (Type[T]): The model class to query.
        **kwargs: Keyword arguments for filtering the query.

    Returns:
        T | None: The first record that matches the given criteria, or None if no match is found.
    """
    session = get_session()
    if session.query(model_class).filter_by(**kwargs).count() > 0:
        return session.query(model_class).filter_by(**kwargs).first()
    return None


def first_or_404(model_class: Type[T], **kwargs) -> T:
    """
    Retrieve the first record that matches the given criteria or raise a 404 error.

    This function retrieves the current SQLAlchemy session and returns the first record
    of the specified model class that matches the provided criteria. If no match is found,
    it raises a 404 error.

    Args:
        model_class (Type[T]): The model class to query.
        **kwargs: Keyword arguments for filtering the query.

    Returns:
        T: The first record that matches the given criteria.

    Raises:
        RuntimeError: If not in a request context.
    """
    if not has_request_context():
        raise RuntimeError("first_or_404 can only be used in a request context.")
    return db.session.query(model_class).filter_by(**kwargs).first_or_404()
