import hashlib
import os
import smtplib

from flask import abort
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.utils import secure_filename

from . import server, datas, config
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
        self.data: datas.User = datas.User.query.filter_by(username=name).first()

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


def send_email(target: str, content: str) -> bool:
    try:
        smtp.sendmail(email_sender, target, content)
    except smtplib.SMTPException:
        smtp.connect(config.smtp.host, config.smtp.port)
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.smtp.user, config.smtp.password)
        try:
            smtp.sendmail(email_sender, target, content)
        except smtplib.SMTPException:
            return False
    return True


def try_hash(content: str | None) -> str:
    if content is None:
        return ""
    return hashlib.sha256(content.encode()).hexdigest()


def gen_key() -> str:
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
    usr = datas.User.query.filter_by(username=user_id)
    if usr.count() == 0:
        usr = datas.User.query.filter_by(email=user_id)
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
    usr = datas.User.query.filter_by(username=user_id)
    if usr.count() == 0:
        usr = datas.User.query.filter_by(email=user_id)
        if usr.count() == 0:
            return None
        user_id = usr.first().username
    return User(user_id)


def exist(user_id: str) -> bool:
    return datas.User.query.filter_by(username=user_id).count() > 0


def create_account(email: str, user_id: str, password: str | None) -> None:
    obj = datas.User(username=user_id.lower(),
                     display_name=user_id,
                     email=email,
                     password_sha256_hex=try_hash(password),
                     permissions="")
    datas.add(obj)


def check_user(require: Permission | None = None, users: list[str] | None = None) -> User:
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
    if not exist("root"):
        create_account("", "root", "root")
        root: datas.User = datas.User.query.filter_by(username="root").first()
        root.permissions = "root"
        datas.add(root)
