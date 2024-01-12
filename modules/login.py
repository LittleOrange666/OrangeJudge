import hashlib
import json
import os.path

from flask_login import LoginManager, UserMixin
from werkzeug.utils import secure_filename

login_manager = None


class User(UserMixin):
    def __init__(self, name: str):
        self.id = secure_filename(name.lower())
        file = f"accounts/{name}/info.json"
        with open(file) as f:
            self.data = json.load(f)

    @property
    def folder(self) -> str:
        return f"accounts/{self.id}/"

    def has(self, key: str) -> bool:
        return key in self.data and bool(self.data[key])


def init_login(app):
    global login_manager
    login_manager = LoginManager(app)
    login_manager.session_protection = None
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def user_loader(name):
        return User(name)


def try_hash(content: str) -> str:
    m = hashlib.sha256()
    m.update(content.encode("utf-8"))
    return m.hexdigest()


def try_login(user_id, password) -> None | User:
    if user_id is None:
        return None
    user_id = secure_filename(user_id)
    if password is None:
        return None
    file = f"accounts/{user_id.lower()}/info.json"
    if not os.path.isfile(file):
        return None
    with open(file) as f:
        data = json.load(f)
    if try_hash(password) != data["password"]:
        return None
    return User(user_id)
