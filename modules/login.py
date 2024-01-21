import hashlib
import os.path
import smtplib

from flask_login import LoginManager, UserMixin
from werkzeug.utils import secure_filename

from modules import tools

login_manager = None
smtp = smtplib.SMTP('smtp.gmail.com', 587)
email_sender = ""


class User(UserMixin):
    def __init__(self, name: str):
        self.id = secure_filename(name.lower())
        self.data = tools.read_json(f"accounts/{self.id}/info.json")

    @property
    def folder(self) -> str:
        return f"accounts/{self.id}/"

    def has(self, key: str) -> bool:
        return key in self.data and bool(self.data[key])


def init_login(app):
    global login_manager, email_sender
    login_manager = LoginManager(app)
    login_manager.session_protection = None
    login_manager.login_view = 'login'
    smtp.ehlo()
    smtp.starttls()
    lines = tools.read("secret/smtp").split("\n")
    email_sender = lines[0]
    smtp.login(lines[0], lines[1])

    @login_manager.user_loader
    def user_loader(name):
        return User(name)


def send_email(target: str, content: str):
    try:
        smtp.sendmail(email_sender, target, content)
    except smtplib.SMTPException:
        smtp.connect('smtp.gmail.com', 587)
        smtp.ehlo()
        smtp.starttls()
        lines = tools.read("secret/smtp").split("\n")
        smtp.login(lines[0], lines[1])
        smtp.sendmail(email_sender, target, content)


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
    if tools.exists(f"verify/used_email", user_id):
        user_id = tools.read(f"verify/used_email", user_id)
    file = f"accounts/{user_id.lower()}/info.json"
    if not os.path.isfile(file):
        return None
    data = tools.read_json(file)
    if try_hash(password) != data["password"]:
        return None
    return User(user_id)


def exist(user_id):
    if user_id is None:
        return None
    user_id = secure_filename(user_id)
    return os.path.isfile(f"accounts/{user_id.lower()}/info.json")


def create_account(email, user_id, password):
    folder = f"accounts/{user_id.lower()}"
    os.makedirs(folder, exist_ok=True)
    dat = {"name": user_id, "DisplayName": user_id, "email": email, "password": try_hash(password)}
    if tools.exists(folder, "info.json"):
        return
    tools.write_json(dat, folder, "info.json")
    tools.create(folder, "problems")
    tools.create(folder, "submissions")
    tools.write(user_id, f"verify/used_email", secure_filename(email))
