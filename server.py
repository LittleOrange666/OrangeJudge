import json
import os.path
import random
import sys
import time
import traceback

from flask import Flask, render_template, request, redirect, session, abort, send_file, Response
from flask_login import login_user, logout_user, login_required, current_user
from flask_session import Session
from flask_wtf import CSRFProtect
from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter
from werkzeug.utils import secure_filename
from yarl import URL

from modules import executing, tasks, tools, problemsetting, constants, login, contests

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}
app = Flask(__name__, static_url_path='/static', static_folder="static/", template_folder="templates/")
app.secret_key = 'HP4xkCix2nf5qCmxSXV0sBwocE2CjECC5z2T9TKQmv8'
app.config['SESSION_TYPE'] = "filesystem"
app.config["SESSION_FILE_DIR"] = "sessions"
app.config["SESSION_COOKIE_NAME"] = "OrangeJudgeSession"
app.config["PERMANENT_SESSION_LIFETIME"] = 3000000
Session(app)
CSRFProtect(app)
login.init(app)


def check_user(require: str | None = None, users: list[str] | None = None) -> login.User:
    obj = request.args if request.method == "GET" else request.form
    username = obj.get('user', current_user.id)
    user = login.get_user(username)
    if user is None:
        abort(404)
    if not user.has("admin"):
        if require is not None and not user.may_has(require):
            abort(403)
        if users is not None and not any(user.in_team(name) for name in users):
            abort(403)
    return user


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.errorhandler(400)
def error_400(error):
    return render_template("400.html"), 400


@app.errorhandler(403)
def error_403(error):
    return render_template("403.html"), 403


@app.errorhandler(404)
def error_404(error):
    return render_template("404.html"), 404


@app.errorhandler(409)
def error_409(error):
    return render_template("404.html"), 409


@app.errorhandler(Exception)
def error_500(error: Exception):
    target = tools.random_string()
    with open(f"logs/{target}.log", "w", encoding="utf-8") as f:
        traceback.print_exception(error, file=f)
    if request.method == "POST":
        return target, 500
    return render_template("500.html", log_uid=target), 500


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/log/<uid>", methods=["GET"])
@login_required
def log(uid):
    check_user("admin")
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
    return redirect('/login')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/')
        return render_template("signup.html")
    email = secure_filename(request.form["email"])
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
    elif tools.exists(f"verify/used_email", email):
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


@app.route('/get_code', methods=['POST'])
def get_code():
    email = request.form["email"]
    if constants.email_reg.match(email) is None:
        abort(400)
    sec_email = secure_filename(email)
    if os.path.exists(f"verify/email/{sec_email}") and os.path.getmtime(f"verify/email/{sec_email}") > time.time() - 60:
        abort(409)
    idx = "".join(str(random.randint(0, 9)) for _ in range(6))
    tools.write(idx, "verify", "email", sec_email)
    if not login.send_email(email, constants.email_content.format(idx)):
        return Response(status=503)
    return Response(status=200)


def use_code(email: str, verify: str) -> bool:
    fn = "verify/email/" + secure_filename(email)
    if len(verify) < 6 or not os.path.exists(fn) or os.path.getmtime(fn) < time.time() - 600 or not tools.read(
            fn).startswith(verify[:6]):
        return False
    tools.remove(fn)
    return True


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/problems', methods=['GET'])
def problems():
    return render_template("problems.html", problems=tools.read_json("data/public_problems.json"))


@app.route('/test', methods=['GET', 'POST'])
@login_required
def test():
    if request.method == 'GET':
        return render_template("test.html", langs=executing.langs.keys())
    else:
        lang = request.form["lang"]
        code = request.form["code"].replace("\n\n", "\n")
        inp = request.form["input"]
        if not inp.endswith("\n"):
            inp += "\n"
        if lang not in executing.langs:
            abort(404)
        ext = executing.langs[lang].data["source_ext"]
        idx = tasks.create_submission()
        if tools.elapsed(current_user.folder, "submissions") < 5:
            abort(429)
        tools.append(idx + "\n", current_user.folder, "submissions")
        tools.write(code, f"submissions/{idx}/a{ext}")
        tools.write(inp, f"submissions/{idx}/in.txt")
        dat = {"type": "test", "source": "a" + ext, "infile": "in.txt", "outfile": "out.txt", "lang": lang,
               "user": current_user.id, "time": tools.get_timestring()}
        tools.write_json(dat, f"submissions/{idx}/info.json")
        tasks.submissions_queue.put(idx)
        return redirect("/submission/" + idx)


@app.route("/submit", methods=['POST'])
@login_required
def submit():
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    pid = request.form["pid"]
    pid = secure_filename(pid)
    if not tools.exists("problems", pid, "info.json"):
        abort(404)
    if lang not in executing.langs:
        abort(404)
    ext = executing.langs[lang].data["source_ext"]
    idx = tasks.create_submission()
    if tools.elapsed(current_user.folder, "submissions") < 5:
        abort(429)
    tools.append(idx + "\n", current_user.folder, "submissions")
    tools.write(code, f"submissions/{idx}/a{ext}")
    dat = {"type": "problem", "source": "a" + ext, "lang": lang, "pid": pid, "user": current_user.id,
           "time": tools.get_timestring()}
    tools.write_json(dat, f"submissions/{idx}/info.json")
    tasks.submissions_queue.put(idx)
    return redirect("/submission/" + idx)


@app.route("/submission/<idx>", methods=['GET'])
@login_required
def submission(idx):
    idx = secure_filename(idx)
    path = "submissions/" + idx
    if not os.path.isdir(path):
        abort(404)
    dat = tools.read_json(path, "info.json")
    lang = dat["lang"]
    source = tools.read(path, dat["source"])
    source = highlight(source, prepares[executing.langs[lang].name], HtmlFormatter())
    completed = os.path.exists(path + "/completed")
    ce_msg = tools.read_default(path, "ce_msg.txt")
    ret = ""
    match dat["type"]:
        case "test":
            if not current_user.has("admin") and dat["user"] != current_user.id:
                abort(403)
            inp = tools.read_default(path, dat["infile"])
            out = tools.read_default(path, dat["outfile"])
            result = tools.read_default(path, "results")
            err = tools.read_default(path, "stderr.txt")
            ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                                  out=out, completed=completed, result=result, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg, je=dat.get("JE", False), logid=dat.get("log_uuid", ""), err=err)
        case "problem":
            pid = dat["pid"]
            problem_path = f"problems/{pid}/"
            group_results = {}
            problem_info = tools.read_json(problem_path, "info.json")
            if not current_user.has("admin") and dat["user"] != current_user.id and current_user.id not in problem_info[
                "users"]:
                abort(403)
            result = {}
            if completed and not dat.get("JE", False):
                result_data = tools.read_json(path, "results.json")
                result["CE"] = result_data["CE"]
                results = result_data["results"]
                result["protected"] = protected = result_data.get("protected", False)
                if not protected:
                    for i in range(len(results)):
                        tcl = len(problem_info["testcases"])
                        it = i if i < tcl else i - tcl
                        test_type = "testcases" if i < tcl else "testcases_gen"
                        results[i] |= problem_info[test_type][it]
                        if results[i]["result"] != "SKIP":
                            results[i]["in"] = tools.read(f"{path}/testcases/{i}.in")
                            results[i]["out"] = tools.read(f"{path}/testcases/{i}.ans")
                        else:
                            results[i]["in"] = results[i]["out"] = ""
                        if results[i].get("has_output", False):
                            results[i]["user_out"] = tools.read(f"{path}/testcases/{i}.out")
                result["results"] = results
                if "group_results" in result_data:
                    gpr = result_data["group_results"]
                    if len(gpr) > 0 and type(next(iter(gpr.values()))) == dict:
                        group_results = gpr
                        for o in group_results.values():
                            o["class"] = constants.result_class.get(o["result"], "")
                if "total_score" in result_data:
                    result["total_score"] = result_data["total_score"]
            ret = render_template("submission/problem.html", lang=lang, source=source, completed=completed,
                                  pname=problem_info["name"], result=result, enumerate=enumerate,
                                  group_results=group_results, pid=pid, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg, je=dat.get("JE", False), logid=dat.get("log_uuid", ""))
        case _:
            abort(404)
    return ret


@app.route("/problem/<idx>", methods=['GET'])
def problem(idx):
    idx = secure_filename(idx)
    path = "problems/" + idx
    if not os.path.isdir(path):
        abort(404)
    dat = tools.read_json(path, "info.json")
    if not dat.get("public", False):
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.has("admin") and current_user.id not in dat.get("users", []):
            abort(403)
    statement = tools.read(path, "statement.html")
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = dat.get("manual_samples", []) + [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
                                               for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if
                                               o.get("sample", False)]
    return render_template("problem.html", dat=dat, statement=statement,
                           langs=executing.langs.keys(), lang_exts=lang_exts, pid=idx,
                           preview=False, samples=enumerate(samples))


@app.route("/problem_file/<idx>/<filename>", methods=['GET'])
def problem_file(idx, filename):
    idx = secure_filename(idx)
    filename = secure_filename(filename)
    dat = tools.read_json("problems", idx, "info.json")
    if not dat.get("public", False):
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.has("admin") and current_user.id not in dat["users"]:
            abort(403)
    target = f"problems/{idx}/public_file/{filename}"
    if not os.path.isfile(target):
        abort(404)
    return send_file(target)


@app.route("/my_submissions", methods=['GET'])
@login_required
def my_submissions():
    submission_list = tools.read(current_user.folder, "submissions").split()
    submit_cnt = len(submission_list)
    page_cnt = (submit_cnt - 1) // constants.page_size + 1
    out = []
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = submission_list[
               max(0, submit_cnt - constants.page_size * page_idx):submit_cnt - constants.page_size * (page_idx - 1)]
    for idx in reversed(got_data):
        o = {"name": idx, "time": "blank", "result": "blank"}
        if not tools.exists(f"submissions/{idx}/info.json"):
            continue
        dat = tools.read_json(f"submissions/{idx}/info.json")
        if "time" in dat:
            o["time"] = dat["time"]
        if not os.path.isfile(f"submissions/{idx}/results.json"):
            o["result"] = "waiting"
        else:
            result = tools.read_json(f"submissions/{idx}/results.json")
            if "simple_result" in result:
                o["result"] = result["simple_result"]
        if dat["type"] == "test":
            o["source"] = "/test"
            o["source_name"] = "Simple Testing"
        else:
            o["source"] = "/problem/" + dat["pid"]
            source_dat = tools.read_json(f"problems/{dat['pid']}/info.json")
            o["source_name"] = source_dat["name"]
        out.append(o)
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("my_submissions.html", submissions=out, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


@app.route("/problemsetting", methods=['GET'])
@login_required
def my_problems():
    user = check_user("make_problems")
    problem_list = tools.read(user.folder, "problems").split()
    problems_dat = []
    for idx in reversed(problem_list):
        # if os.path.isfile(f"preparing_problems/{idx}.img") and not os.path.isfile(
        #         f"preparing_problems/{idx}/info.json"):
        #     problemsetting.system(f"sudo mount -o loop {idx}.img ./{idx}", "preparing_problems")
        if not tools.exists(f"preparing_problems/{idx}/info.json"):
            continue
        dat = tools.read_json(f"preparing_problems/{idx}/info.json")
        problems_dat.append({"pid": idx, "name": dat["name"]})
    return render_template("my_problems.html", problems=problems_dat, username=user.id)


@app.route("/problemsetting_new", methods=['GET', 'POST'])
@login_required
def create_problem():
    user = check_user("make_problems")
    if request.method == "GET":
        return render_template("create_problem.html")
    else:
        idx = problemsetting.create_problem(request.form["name"], user.id)
        tools.append(idx + "\n", user.folder, "problems")
        return redirect(f"/problemsetting/{idx}?user={user.id}")


@app.route("/problemsetting/<idx>", methods=['GET'])
@login_required
def my_problem_page(idx):
    idx = secure_filename(idx)
    if not os.path.isdir("preparing_problems/" + idx) or not os.path.isfile("preparing_problems/" + idx + "/info.json"):
        abort(404)
    # if len(os.listdir("preparing_problems/" + idx)) == 0:
    #     problemsetting.system(f"sudo mount -o loop {idx}.img ./{idx}", "preparing_problems")
    o = problemsetting.check_background_action(idx)
    if o is not None:
        return render_template("pleasewaitlog.html", action=o[1], log=o[0])
    dat = tools.read_json("preparing_problems", idx, "info.json")
    user = check_user("make_problems", dat["users"])
    public_files = os.listdir(f"preparing_problems/{idx}/public_file")
    try:
        public_files.remove(".gitkeep")
    except ValueError:
        pass
    default_checkers = [s for s in os.listdir("testlib/checkers") if s.endswith(".cpp")]
    default_interactors = [s for s in os.listdir("testlib/interactors") if s.endswith(".cpp")]
    if "groups" not in dat or "default" not in dat["groups"]:
        if "groups" not in dat:
            dat["groups"] = {}
        if "default" not in dat["groups"]:
            dat["groups"]["default"] = {}
        tools.write_json(dat, "preparing_problems", idx, "info.json")
    return render_template("problemsetting.html", dat=constants.default_problem_info | dat, pid=idx,
                           versions=problemsetting.query_versions(idx), enumerate=enumerate,
                           public_files=public_files, default_checkers=default_checkers,
                           langs=executing.langs.keys(), default_interactors=default_interactors,
                           username=user.id)


@app.route("/problemsetting_action", methods=['POST'])
@login_required
def problem_action():
    idx = request.form["pid"]
    idx = secure_filename(idx)
    if not os.path.isfile(f"preparing_problems/{idx}/info.json"):
        abort(404)
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        abort(503)
    if problemsetting.check_background_action(idx) is not None:
        abort(503)
    dat = tools.read_json(f"preparing_problems/{idx}/info.json")
    user = check_user("make_problems", dat["users"])
    return problemsetting.action(request.form)


@app.route("/problemsetting_preview", methods=["GET"])
@login_required
def problem_preview():
    idx = request.args["pid"]
    idx = secure_filename(idx)
    if not os.path.isfile(f"preparing_problems/{idx}/info.json"):
        abort(404)
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        return render_template("pleasewait.html", action=tools.read("preparing_problems", idx, "waiting"))
    dat = tools.read_json(f"preparing_problems/{idx}/info.json")
    user = check_user("make_problems", dat["users"])
    return problemsetting.preview(request.args)


@app.route("/user/<name>", methods=["GET"])
def user_page(name):
    name = name.lower()
    if not login.exist(name):
        abort(404)
    return render_template("user.html", name=name, data=login.get_user(name).data)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    data = current_user.data
    if request.method == "GET":
        teams = {k: login.get_user(k).data for k in data.get("teams", [])}
        perms = [(k, v) for k, v in constants.permissions.items() if current_user.has(k) and k != "admin"]
        return render_template("settings.html", data=data, teams=teams, perms=perms)
    if request.form["action"] == "general_info":
        data["DisplayName"] = request.form.get("DisplayName", data["DisplayName"])
    elif request.form["action"] == "change_password":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        if login.try_hash(old_password) != data["password"]:
            abort(403)
        if len(new_password) < 6:
            abort(400)
        data["password"] = login.try_hash(new_password)
    elif request.form["action"] == "create_team":
        name = request.form["name"].lower()
        if not name:
            abort(400)
        if login.exist(name):
            abort(409)
        perms = [k for k in constants.permissions if current_user.has(k) and k != "admin" and
                 request.form.get("perm_" + k, "") == "on"]
        login.create_team(name, current_user.id, perms)
        if "teams" not in data:
            data["teams"] = []
        data["teams"].append(name)
    elif request.form["action"] == "add_member":
        target = request.form["target"].lower()
        name = request.form["team"].lower()
        if not login.exist(target):
            abort(404)
        if not login.exist(name) or not login.get_user(name).data["owner"] == current_user.id:
            abort(403)
        team = login.get_user(name)
        user = login.get_user(target)
        team_data = team.data
        user_data = user.data
        if target in team_data["members"]:
            abort(409)
        if "teams" not in user_data:
            user_data["teams"] = []
        if name in user_data["teams"]:
            abort(409)
        team_data["members"].append(target)
        user_data["teams"].append(name)
        user.data = user_data
        team.data = team_data
    elif request.form["action"] == "leave_team":
        name = request.form["team"].lower()
        team = login.get_user(name)
        team_data = team.data
        if current_user.id not in team_data["members"]:
            abort(409)
        if name not in data.get("teams", []):
            abort(409)
        data["teams"].remove(name)
        team_data["members"].remove(current_user.id)
        team.data = team_data
    current_user.data = data
    return "", 200


@app.route("/forget_password", methods=["GET", "POST"])
def forget_password():
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
    data["password"] = login.try_hash(password)
    user.data = data
    return "", 200


@app.route("/contests", methods=["GET"])
def contests_list():
    contest_list = tools.read("data/public_contests").split()
    contest_cnt = len(contest_list)
    page_cnt = max((contest_cnt - 1) // constants.page_size + 1, 1)
    out = []
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = contest_list[
               max(0, contest_cnt - constants.page_size * page_idx):contest_cnt - constants.page_size * (page_idx - 1)]
    for idx in got_data:
        o = tools.read_json("contests", idx, "info.json")
        o["idx"] = idx
        out.append(o)
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("contests.html", contests=out, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


@app.route("/create_contest", methods=["POST"])
@login_required
def create_contest():
    check_user("make_problems")
    name = request.form["contest_name"]
    if not name:
        abort(400)
    idx = contests.create_contest(name, current_user.id)
    return "/contest/"+idx, 200


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The judge server only supports Linux")
    if not executing.call(["whoami"])[0].startswith("root\n"):
        raise RuntimeError("The judge server must be run as root")
    problemsetting.system(f"sudo lxc-start {constants.lxc_name}")
    problemsetting.system(f"sudo cp -r -f judge /var/lib/lxc/{constants.lxc_name}/rootfs/")
    executing.init()
    tasks.init()
    problemsetting.init()
    app.run("0.0.0.0", port=8898)


if __name__ == '__main__':
    main()
