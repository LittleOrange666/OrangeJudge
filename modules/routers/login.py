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

import random
import time
from urllib.parse import urlparse

import flask
from flask import abort, render_template, redirect, request, Response
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename

from .. import tools, server, login, constants, datas, locks, config
from ..constants import log_path
from ..objs import Permission

app = server.app


@app.route("/log/<uid>", methods=["GET"])
@login_required
def log(uid):
    if not current_user.has(Permission.admin):
        abort(403)
    uid = secure_filename(uid)
    path = log_path / f"{uid}.log"
    if not path.exists():
        abort(404)
    return render_template("log.html", content=tools.read(path))


def bad_url(url):
    o = urlparse(url)
    return o.path.startswith("/login") or o.path.startswith("/signup") or o.netloc != request.host


@app.route('/login', methods=['GET', 'POST'])
def do_login():
    if request.method == 'GET':
        link = request.referrer
        if current_user.is_authenticated:
            if "referrer" in flask.session:
                link = flask.session["referrer"]
                del flask.session["referrer"]
            if bad_url(link):
                return redirect("/")
            return redirect(link)
        if not bad_url(link) and "referrer" not in flask.session:
            flask.session["referrer"] = request.referrer
        return render_template("login.html")
    name = request.form.get('user_id')
    user, msg = login.try_login(name, request.form.get('password'))
    if user is not None:
        login_user(user)
        return msg, 200
    return msg, 403


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if not config.account.signup:
        abort(503)
    need_verify = config.smtp.enabled
    if request.method == 'GET':
        link = request.referrer
        if current_user.is_authenticated:
            if "referrer" in flask.session:
                link = flask.session["referrer"]
                del flask.session["referrer"]
            if bad_url(link):
                return redirect("/")
            return redirect(link)
        if not bad_url(link) and "referrer" not in flask.session:
            flask.session["referrer"] = request.referrer
        return render_template("signup.html", need_verify=need_verify)
    email = request.form["email"]
    verify = request.form["verify"] if need_verify else ""
    user_id = request.form["user_id"]
    password = request.form["password"]
    password_again = request.form["password_again"]
    if constants.user_id_reg.match(user_id) is None:
        return "ID不合法", 400
    if login.exist(user_id):
        return "ID已被使用", 400
    if datas.count(datas.User, email=email) > 0:
        return "email已被使用", 400
    if len(password) < 6:
        return "密碼應至少6個字元", 400
    if password != password_again:
        return "重複密碼不一致", 400
    if need_verify and not use_code(email, verify):
        return "驗證碼錯誤", 400
    login.create_account(email, user_id, password)
    with datas.SessionContext():
        user, msg = login.try_login(user_id, password)
        if user is None:
            return "註冊失敗: " + msg, 400
        login_user(user)
    return "OK", 200


verify_codes = locks.manager.dict()


@app.route('/get_code', methods=['POST'])
@server.limiter.limit(config.smtp.limit, override_defaults=False)
def get_code():
    email = request.form["email"]
    if constants.email_reg.match(email) is None:
        abort(400)
    if email in verify_codes and verify_codes[email][1] > time.time() - 60:
        abort(409)
    idx = "".join(str(random.randint(0, 9)) for _ in range(6))
    verify_codes[email] = (idx, time.time())
    if not config.smtp.enabled:
        abort(503)
    if not login.send_code(email, idx):
        abort(503)
    return Response(status=200)


def use_code(email: str, verify: str) -> bool:
    if email not in verify_codes:
        return False
    dat = verify_codes[email]
    if dat[1] < time.time() - 600:
        del verify_codes[email]
        return False
    if dat[0] != verify[:6]:
        return False
    del verify_codes[email]
    return True


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(request.referrer)


@app.route("/user/<name>", methods=["GET"])
def user_page(name):
    name = name.lower()
    if not login.exist(name):
        abort(404)
    return render_template("user.html", name=name, data=login.get_user(name).data)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    data: datas.User = current_user.data
    if request.method == "GET":
        perms = [(perm.name, perm.value) for perm in Permission if current_user.has(perm) and
                 perm not in (Permission.admin, Permission.root)]
        return render_template("settings.html", data=data, perms=perms)
    if request.form["action"] == "general_info":
        display_name = request.form["DisplayName"]
        if len(display_name) > 120 or len(display_name) < 1:
            abort(400)
        data.display_name = display_name
        current_user.save()
    elif request.form["action"] == "change_password":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        if login.try_hash(old_password) != data.password_sha256_hex:
            abort(403)
        if len(new_password) < 6:
            abort(400)
        data.password_sha256_hex = login.try_hash(new_password)
        current_user.save()
    return "", 200


@app.route("/gen_key", methods=["POST"])
@login_required
def gen_key():
    data: datas.User = current_user.data
    key = login.gen_key()
    data.api_key = login.try_hash(key)
    current_user.save()
    return key, 200


@app.route("/forget_password", methods=["GET", "POST"])
def forget_password():
    if not config.smtp.enabled:
        abort(503)
    if current_user.is_authenticated:
        abort(409)
    if request.method == "GET":
        return render_template("forget_password.html")
    email = request.form["email"]
    verify = request.form["verify"]
    password = request.form["password"]
    user = login.get_user(email)
    if user is None:
        abort(404)
    if not use_code(email, verify):
        abort(403)
    data = user.data
    data.password_sha256_hex = login.try_hash(password)
    user.save()
    return "", 200
