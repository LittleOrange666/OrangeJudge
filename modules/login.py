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

import hashlib
import os
import smtplib
from email.message import EmailMessage

from flask import abort
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.utils import secure_filename

from . import server, datas, config, constants
from .objs import Permission

smtp = smtplib.SMTP(config.smtp.host, config.smtp.port)


class User(UserMixin):
    """
    Represents a user in the website.

    This class extends UserMixin and provides methods for user management,
    including permission checking and data persistence.
    """

    def __init__(self, name: str):
        """
        Initialize a User object.

        Args:
            name (str): The username of the user.
        """
        self.id = secure_filename(name.lower())
        self.data: datas.User = datas.first(datas.User, username=name)

    def save(self):
        """
        Save the user data to the database.
        """
        datas.add(self.data)

    @property
    def folder(self) -> str:
        """
        Get the user's account folder path.

        Returns:
            str: The path to the user's account folder.
        """
        return f"accounts/{self.id}/"

    def has_str(self, key: str) -> bool:
        """
        Check if the user has a specific permission using a string key.

        Args:
            key (str): The permission key to check.

        Returns:
            bool: True if the user has the permission, False otherwise.
        """
        return self.has(Permission[key])

    def has(self, key: Permission) -> bool:
        """
        Check if the user has a specific permission.

        Args:
            key (Permission): The permission to check.

        Returns:
            bool: True if the user has the permission, False otherwise.
        """
        perms = self.data.permission_list()
        if key.name in perms or Permission.root.name in perms:
            return True
        if key is not Permission.root:
            return Permission.admin.name in perms
        return False

    def check_api_key(self, key: str) -> bool:
        """
        Check if the user has a specific API key.

        Args:
            key (str): The API key to check.

        Returns:
            bool: True if the user has the API key, False otherwise.
        """
        return self.data.api_key == try_hash(key)


app = server.app
login_manager = LoginManager(app)
login_manager.session_protection = None
login_manager.login_view = 'do_login'
email_sender = config.smtp.user


@login_manager.user_loader
def user_loader(name):
    return get_user(name)


def send_mail(msg: EmailMessage, target: str) -> bool:
    msg["From"] = email_sender
    msg["To"] = target
    try:
        smtp.send_message(msg)
    except smtplib.SMTPException:
        smtp.connect(config.smtp.host, config.smtp.port)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.smtp.user, config.smtp.password)
        try:
            smtp.send_message(msg)
        except smtplib.SMTPException:
            return False
    return True


def send_code(target: str, idx: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = constants.email_subject.format(idx)
    msg.set_content(constants.email_content.format(idx))
    return send_mail(msg, target)


def try_hash(content: str | None) -> str:
    """
    Hash the given content using SHA-256.

    This function takes a string input, encodes it, and returns its SHA-256 hash
    in hexadecimal format. If the input is None, it returns an empty string.

    Args:
        content (str | None): The content to be hashed.

    Returns:
        str: The SHA-256 hash of the content in hexadecimal format, or an empty string if the input is None.
    """
    if content is None:
        return ""
    return hashlib.sha256(content.encode()).hexdigest()


def gen_key() -> str:
    """
    Generate a random SHA-256 hash key.

    This function generates a random 32-byte string using os.urandom,
    then computes and returns its SHA-256 hash in hexadecimal format.

    Returns:
        str: A SHA-256 hash key in hexadecimal format.
    """
    return hashlib.sha256(os.urandom(32)).hexdigest()


def try_login(user_id: str, password: str) -> tuple[None | User, str]:
    """
    Attempt to log in a user with the provided credentials.

    This function tries to authenticate a user using either their username or email,
    and the provided password. It performs various checks and returns appropriate
    messages based on the authentication result.

    Args:
        user_id (str): The user's identifier, which can be either a username or an email address.
        password (str): The user's password for authentication.

    Returns:
        tuple[None | User, str]: A tuple containing two elements:
            - The first element is either a User object if login is successful, or None if it fails.
            - The second element is a string message describing the result of the login attempt.

    Note:
        The function converts the user_id to lowercase before processing.
    """
    user_id = user_id.lower()
    if password is None:
        return None, "密碼不能為空"
    usr = datas.filter_by(datas.User, username=user_id)
    if usr.count() == 0:
        usr = datas.filter_by(datas.User, email=user_id)
        if usr.count() == 0:
            return None, "帳號或密碼錯誤"
        user_id = usr.first().username
    if usr.count() > 1:
        return None, "帳號資料異常"
    pwd = usr.first().password_sha256_hex
    if pwd != try_hash(password):
        return None, "帳號或密碼錯誤"
    return User(user_id), "登入成功"


def get_user(user_id: str) -> User | None:
    """
    Retrieve a User object based on the provided user identifier.

    This function attempts to find a user by their username first. If no user is found,
    it then tries to find the user by their email address. If a user is found by email,
    the function updates the user_id to the corresponding username.

    Args:
        user_id (str): The user's identifier, which can be either a username or an email address.

    Returns:
        User | None: A User object if the user is found, or None if no user is found.
    """
    usr = datas.filter_by(datas.User, username=user_id)
    if usr.count() == 0:
        usr = datas.filter_by(datas.User, email=user_id)
        if usr.count() == 0:
            return None
        user_id = usr.first().username
    return User(user_id)


def exist(user_id: str) -> bool:
    return datas.count(datas.User, username=user_id.lower()) > 0


def create_account(email: str, user_id: str, password: str | None, display_name: str | None = None) -> None:
    if display_name is None:
        display_name = user_id
    with datas.SessionContext():
        obj = datas.User(username=user_id.lower(),
                         display_name=display_name,
                         email=email,
                         password_sha256_hex=try_hash(password),
                         permissions="")
        datas.add(obj)


def has_permission(key: Permission) -> bool:
    return current_user.is_authenticated and current_user.has(key)


def check_user(require: Permission | None = None, users: list[str] | None = None) -> User:
    """
    Check the current user's authentication and permissions.

    This function verifies if the current user is authenticated and has the required permissions.
    If the user is not authenticated or does not have the necessary permissions, it aborts with a 403 error.

    Args:
        require (Permission | None): The required permission to check. Defaults to None.
        users (list[str] | None): A list of user IDs to check against. Defaults to None.

    Returns:
        User: The current authenticated user.

    Raises:
        werkzeug.exceptions.HTTPException: If the user is not authenticated or does not have the required permissions.
    """
    user: User = current_user
    if not user.is_authenticated:
        abort(403)
    if not user.has(Permission.admin):
        if require is not None and not user.has(require):
            abort(403)
        if users is not None and user.id not in users:
            abort(403)
    return user


def init():
    if config.smtp.enabled:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.smtp.user, config.smtp.password)
    with datas.SessionContext():
        if not exist("root"):
            create_account("", "root", "root")
            root = datas.first(datas.User, username="root")
            root.permissions = "root"
            datas.add(root)
            if datas.count(datas.Problem, pid="test") == 0:
                test_problem = datas.Problem(pid="test", name="", data={}, new_data={}, user=root)
                datas.add(test_problem)
