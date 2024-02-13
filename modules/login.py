import hashlib
import json
import os.path
import smtplib
from multiprocessing import Lock
from multiprocessing.managers import DictProxy

from flask import Flask
from flask_login import LoginManager, UserMixin
from werkzeug.utils import secure_filename

from modules import tools, locks

login_manager = None
smtp = smtplib.SMTP('smtp.gmail.com', 587)
email_sender = ""


class UserDataManager:
    def __init__(self):
        self.mp: DictProxy[str, str] = locks.manager.dict()
        self.lock = Lock()

    def read(self, name: str) -> dict:
        with self.lock:
            if name not in self.mp:
                self.mp[name] = tools.read(f"accounts/{name}/info.json")
            return json.loads(self.mp[name])

    def write(self, name: str, value: dict):
        with self.lock:
            self.mp[name] = json.dumps(value, indent=2)
            tools.write(self.mp[name], f"accounts/{name}/info.json")

    def save(self):
        for name, value in self.mp.items():
            tools.write(value, f"accounts/{name}/info.json")

    def __del__(self):
        self.save()


user_data_manager = UserDataManager()


class User(UserMixin):
    def __init__(self, name: str):
        self.id = secure_filename(name.lower())

    @property
    def data(self) -> dict:
        return user_data_manager.read(self.id)

    @data.setter
    def data(self, value: dict):
        user_data_manager.write(self.id, value)

    @property
    def folder(self) -> str:
        return f"accounts/{self.id}/"

    def has(self, key: str) -> bool:
        return key in self.data and bool(self.data[key]) or "admin" in self.data and bool(self.data["admin"])

    def may_has(self, key: str) -> bool:
        if self.has(key):
            return True
        return "teams" in self.data and any(User(k).has(key) for k in self.data["teams"])

    def who_has(self, key: str) -> list[str]:
        ret = []
        if self.has(key):
            ret.append(self.id)
        if "teams" in self.data:
            for k in self.data["teams"]:
                if User(k).has(key):
                    ret.append(k)
        return ret

    def in_team(self, key: str) -> bool:
        return self.id == key or "teams" in self.data and key in self.data["teams"]

    def is_team(self) -> bool:
        return self.has("team")


def init(app: Flask) -> None:
    global login_manager, email_sender
    login_manager = LoginManager(app)
    login_manager.session_protection = None
    login_manager.login_view = 'do_login'
    smtp.ehlo()
    smtp.starttls()
    lines = tools.read("secret/smtp").split("\n")
    email_sender = lines[0]
    smtp.login(lines[0], lines[1])

    @login_manager.user_loader
    def user_loader(name):
        return User(name)


def send_email(target: str, content: str) -> bool:
    try:
        smtp.sendmail(email_sender, target, content)
    except smtplib.SMTPException:
        smtp.connect('smtp.gmail.com', 587)
        smtp.ehlo()
        smtp.starttls()
        lines = tools.read("secret/smtp").split("\n")
        smtp.login(lines[0], lines[1])
        try:
            smtp.sendmail(email_sender, target, content)
        except smtplib.SMTPException:
            return False
    return True


def try_hash(content: str | None) -> str:
    if content is None:
        return ""
    m = hashlib.sha256()
    m.update(content.encode("utf-8"))
    return m.hexdigest()


def try_login(user_id: str, password: str) -> None | User:
    user_id = secure_filename(user_id)
    if password is None:
        return None
    if tools.exists(f"verify/used_email", user_id):
        user_id = tools.read(f"verify/used_email", user_id)
    file = f"accounts/{user_id.lower()}/info.json"
    if not os.path.isfile(file):
        return None
    data = tools.read_json(file)
    if try_hash(password) != data["password"]:
        return None
    return User(user_id)


def get_user(user_id: str) -> User | None:
    if tools.exists(f"verify/used_email", secure_filename(user_id)):
        user_id = tools.read(f"verify/used_email", secure_filename(user_id))
    file = f"accounts/{user_id.lower()}/info.json"
    if not os.path.isfile(file):
        return None
    return User(user_id)


def exist(user_id: str) -> bool:
    user_id = secure_filename(user_id)
    return os.path.isfile(f"accounts/{user_id.lower()}/info.json")


def create_account(email: str, user_id: str, password: str | None, is_team: bool = False) -> None:
    folder = f"accounts/{user_id.lower()}"
    os.makedirs(folder, exist_ok=True)
    dat = {"name": user_id, "DisplayName": user_id, "email": email, "password": try_hash(password),
           "team": is_team}
    if tools.exists(folder, "info.json"):
        return
    if tools.exists(f"verify/used_email", secure_filename(email)):
        return
    tools.write_json(dat, folder, "info.json")
    tools.create(folder, "problems")
    tools.create(folder, "submissions")
    tools.create(folder, "contests")
    tools.write(user_id, f"verify/used_email", secure_filename(email))


def create_team(team_id: str, owner_id: str, permissions: list[str]):
    folder = f"accounts/{team_id.lower()}"
    os.makedirs(folder, exist_ok=True)
    dat = {"name": team_id, "DisplayName": team_id, "owner": owner_id, "members": [owner_id]}
    for k in permissions:
        dat[k] = True
    if tools.exists(folder, "info.json"):
        return
    tools.write_json(dat, folder, "info.json")
    tools.create(folder, "problems")
    tools.create(folder, "submissions")
    tools.create(folder, "contests")
