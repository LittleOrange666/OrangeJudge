import random
import time

from flask import abort, render_template, redirect, request, Response
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.utils import secure_filename
from yarl import URL

from ..constants import Permission
from .. import tools, server, login, constants, datas, locks, config

app = server.app


@app.route("/log/<uid>", methods=["GET"])
@login_required
def log(uid):
    if not current_user.has(Permission.admin):
        abort(403)
    uid = secure_filename(uid)
    if not tools.exists("logs", uid + ".log"):
        abort(404)
    return render_template("log.html", content=tools.read("logs", uid + ".log"))


@app.route('/login', methods=['GET', 'POST'])
def do_login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/')
        return render_template("login.html")
    nxt = request.form.get('next')
    name = request.form['user_id']
    user = login.try_login(name, request.form['password'])
    if user is not None:
        login_user(user)
        return redirect(nxt or '/')
    if nxt:
        return redirect(f'/login?next={nxt}#fail')
    else:
        return redirect('/login#fail')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if not config.account.signup.value:
        abort(503)
    need_verify = config.smtp.enabled.value
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/')
        return render_template("signup.html", need_verify=need_verify)
    email = request.form["email"]
    verify = request.form["verify"] if need_verify else ""
    user_id = request.form["user_id"]
    password = request.form["password"]
    nxt = request.form.get('next')
    url = URL(request.referrer)
    err = ""
    if constants.user_id_reg.match(user_id) is None:
        err = "ID不合法"
    elif login.exist(user_id):
        err = "ID已被使用"
    elif datas.User.query.filter_by(email=email).count() > 0:
        err = "email已被使用"
    elif len(password) < 6:
        err = "密碼應至少6個字元"
    elif need_verify and not use_code(email, verify):
        err = "驗證碼錯誤"
    if err:
        q = {"msg": err}
        q.update(url.query)
        return redirect(str(url.with_query(q)))
    login.create_account(email, user_id, password)
    user = login.try_login(user_id, password)
    if user is None:
        err = "註冊失敗"
        q = {"msg": err}
        q.update(url.query)
        return redirect(str(url.with_query(q)))
    login_user(user)
    return redirect(nxt or '/')


verify_codes = locks.manager.dict()


@app.route('/get_code', methods=['POST'])
@server.limiter.limit("1/20second", override_defaults=False)
def get_code():
    email = request.form["email"]
    if constants.email_reg.match(email) is None:
        abort(400)
    if email in verify_codes and verify_codes[email][1] > time.time() - 60:
        abort(409)
    idx = "".join(str(random.randint(0, 9)) for _ in range(6))
    verify_codes[email] = (idx, time.time())
    if not config.smtp.enabled.value:
        abort(503)
    if not login.send_email(email, constants.email_content.format(idx)):
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
    return redirect("/")


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


@app.route("/forget_password", methods=["GET", "POST"])
def forget_password():
    if not config.smtp.enabled.value:
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
