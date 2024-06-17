import random
import time

from flask import abort, render_template, redirect, request, Response
from flask_login import login_required, current_user, login_user, logout_user
from yarl import URL

from modules import tools, server, login, constants, datas, locks, config

app = server.app


@app.route("/log/<uid>", methods=["GET"])
@login_required
def log(uid):
    # login.check_user("admin")
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
    if not config.get('account.signup'):
        abort(503)
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/')
        return render_template("signup.html")
    email = request.form["email"]
    verify = request.form["verify"]
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
    elif not use_code(email, verify):
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
    if config.get("smtp.enabled"):
        if not login.send_email(email, constants.email_content.format(idx)):
            return Response(status=503)
        return Response(status=200)
    else:
        return idx, 200


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
        teams = {k: login.get_user(k).data for k in data.team_list()}
        perms = [(k, v) for k, v in constants.permissions.items() if current_user.has(k) and k != "admin"
                 and k != "root"]
        return render_template("settings.html", data=data, teams=teams, perms=perms)
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
    elif request.form["action"] == "create_team":
        name = request.form["name"].lower()
        if not name:
            abort(400)
        if login.exist(name):
            abort(409)
        perms = [k for k in constants.permissions if current_user.has(k) and k != "admin" and
                 request.form.get("perm_" + k, "") == "on"]
        login.create_team(name, current_user.id, perms)
        data.add_team(name)
        current_user.save()
    elif request.form["action"] == "add_member":
        target = request.form["target"].lower()
        name = request.form["team"].lower()
        if not login.exist(target):
            abort(404)
        if not login.exist(name) or not login.get_user(name).data.owner_id == data.id:
            abort(403)
        user = login.get_user(target)
        user_data = user.data
        if name in user_data.team_list():
            abort(409)
        user_data.add_team(name)
        user.save()
        current_user.save()
    elif request.form["action"] == "leave_team":
        name = request.form["team"].lower()
        if name not in data.team_list():
            abort(409)
        data.remove_team(name)
        current_user.save()
    return "", 200


@app.route("/forget_password", methods=["GET", "POST"])
def forget_password():
    if not config.get("smtp.enabled"):
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
