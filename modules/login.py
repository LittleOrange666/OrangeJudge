import hashlib
import json
import os.path
import smtplib

from flask import request, abort
from flask_login import LoginManager, UserMixin, current_user
from werkzeug.utils import secure_filename

from modules import tools, server, datas

smtp = smtplib.SMTP('smtp.gmail.com', 587)


class User(UserMixin):
    def __init__(self, name: str):
        self.id = secure_filename(name.lower())
        self.data: datas.User = datas.User.query.filter_by(username=name).first()

    def save(self):
        datas.add(self.data)

    @property
    def folder(self) -> str:
        return f"accounts/{self.id}/"

    def has(self, key: str) -> bool:
        prems = self.data.permission_list()
        return key in prems or "admin" in prems

    def may_has(self, key: str) -> bool:
        if self.has(key):
            return True
        return any(User(k).has(key) for k in self.data.team_list())

    """
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
    """


app = server.app
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
    return get_user(name)


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
    user_id = user_id.lower()
    if password is None:
        return None
    usr = datas.User.query.filter_by(username=user_id)
    if usr.count() == 0:
        usr = datas.User.query.filter_by(email=user_id)
        if usr.count() == 0:
            return None
        user_id = usr.first().username
    pwd = usr.first().password_sha256_hex
    if pwd != try_hash(password):
        return None
    return User(user_id)


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


def create_account(email: str, user_id: str, password: str | None, is_team: bool = False) -> None:
    obj = datas.User(username=user_id.lower(),
                     display_name=user_id,
                     email=email,
                     password_sha256_hex=try_hash(password),
                     permissions="",
                     teams="",
                     is_team=is_team)
    datas.add(obj)
    """
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
    """


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


def check_user(require: str | None = None, users: list[str] | None = None) -> User:
    obj = request.args if request.method == "GET" else request.form
    username = obj.get('user', current_user.id)
    user = get_user(username)
    if user is None:
        abort(404)
    if not user.has("admin"):
        if require is not None and not user.may_has(require):
            abort(403)
        if users is not None and not any(user.in_team(name) for name in users):
            abort(403)
    return user


def init():
    pass
