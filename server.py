import json
import os.path
import random
import sys
import time

from flask import Flask, render_template, request, redirect, session, abort, send_file, Response
from flask_login import login_user, logout_user, login_required, current_user
from flask_session import Session
from yarl import URL
from werkzeug.utils import secure_filename

from modules import executing, tasks, tools, problemsetting, constants
from modules.login import try_login, init_login, send_email, exist, create_account
from modules.constants import result_class, lxc_name

from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}
app = Flask(__name__, static_url_path='/static', static_folder="static/", template_folder="templates/")
app.secret_key = 'HP4xkCix2nf5qCmxSXV0sBwocE2CjECC5z2T9TKQmv8'
app.config['SESSION_TYPE'] = "filesystem"
app.config["SESSION_FILE_DIR"] = "sessions"
app.config["SESSION_COOKIE_NAME"] = "OrangeJudgeSession"
Session(app)
init_login(app)


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect('/')
        return render_template("login.html")
    nxt = request.form.get('next')
    name = request.form['user_id']
    user = try_login(name, request.form['password'])
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
    email = request.form["email"]
    fn = "verify/" + secure_filename(email)
    verify = request.form["verify"]
    user_id = request.form["user_id"]
    password = request.form["password"]
    nxt = request.form.get('next')
    url = URL(request.referrer)
    err = ""
    if len(verify) != 6 or not os.path.exists(fn) or os.path.getmtime(fn) < time.time() - 600 or not tools.read(
            fn).startswith(verify):
        err = "驗證碼錯誤"
    elif constants.user_id_reg.match(user_id) is None:
        err = "ID不合法"
    elif exist(user_id):
        err = "ID已被使用"
    elif len(password) < 6:
        err = "密碼應至少6個字元"
    if err:
        q = {"msg": err}
        q.update(url.query)
        return redirect(str(url.with_query(q)))
    create_account(email, user_id, password)
    user = try_login(user_id, password)
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
    if os.path.exists(f"verify/{sec_email}") and os.path.getmtime(f"verify/{sec_email}") > time.time() - 60:
        abort(400)
    idx = "".join(str(random.randint(0, 9)) for _ in range(6))
    tools.write(idx, "verify", sec_email)
    send_email(email, constants.email_content.format(idx))
    return Response(status=200)


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
    if not current_user.has("admin") and dat["user"] != current_user.id:
        abort(403)
    lang = dat["lang"]
    source = tools.read(path, dat["source"])
    source = highlight(source, prepares[executing.langs[lang].name], HtmlFormatter())
    completed = os.path.exists(path + "/completed")
    ce_msg = tools.read_default(path, "ce_msg.txt")
    match dat["type"]:
        case "test":
            inp = tools.read(path, dat["infile"])
            out = tools.read_default(path, dat["outfile"])
            result = tools.read_default(path, "result")
            ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                                  out=out, completed=completed, result=result, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg)
        case "problem":
            pid = dat["pid"]
            problem_path = f"problems/{pid}/"
            group_results = {}
            problem_info = tools.read_json(problem_path, "info.json")
            result = {}
            if completed:
                result_data = tools.read_json(path, "result.json")
                result["CE"] = result_data["CE"]
                results = result_data["results"]
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
                            o["class"] = result_class.get(o["result"], "")
            ret = render_template("submission/problem.html", lang=lang, source=source, completed=completed,
                                  pname=problem_info["name"], result=result, enumerate=enumerate,
                                  group_results=group_results, pid=pid, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg)
        case _:
            abort(404)
    return ret


@app.route("/problem/<idx>", methods=['GET'])
def problem(idx):
    idx = secure_filename(idx)
    path = "problems/" + idx
    if not os.path.isdir(path):
        abort(404)
    if (os.path.isfile(path + "/rendered.html") and
            os.path.getmtime(path + "/rendered.html") >= os.path.getmtime(path + "/info.json")):
        return tools.read(path, "rendered.html")
    dat = tools.read_json(path, "info.json")
    statement = tools.read(path, "statement.html")
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
               for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if o.get("sample", False)]
    ret = render_template("problem.html", dat=dat, statement=statement,
                          langs=executing.langs.keys(), lang_exts=lang_exts, pid=idx,
                          preview=False, samples=enumerate(samples))
    tools.write(path, "rendered.html", ret)
    return ret


@app.route("/problem_file/<idx>/<filename>", methods=['GET'])
def problem_file(idx, filename):
    idx = secure_filename(idx)
    filename = secure_filename(filename)
    target = f"problems/{idx}/public_file/{filename}"
    if not os.path.isfile(target):
        abort(404)
    return send_file(target)


@app.route("/my_submissions", methods=['GET'])
@login_required
def my_submissions():
    submission_list = tools.read(current_user.folder, "submissions").split()
    out = []
    for idx in reversed(submission_list):
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
    return render_template("my_submissions.html", submissions=out)


@app.route("/problemsetting", methods=['GET'])
@login_required
def my_problems():
    if not current_user.has("make_problems"):
        abort(403)
    problem_list = tools.read(current_user.folder, "problems").split()
    problems_dat = []
    for idx in reversed(problem_list):
        if os.path.isfile(f"preparing_problems/{idx}.img") and not os.path.isfile(
                f"preparing_problems/{idx}/info.json"):
            problemsetting.system(f"sudo mount -o loop {idx}.img ./{idx}", "preparing_problems")
        dat = tools.read_json(f"preparing_problems/{idx}/info.json")
        problems_dat.append({"pid": idx, "name": dat["name"]})
    return render_template("my_problems.html", problems=problems_dat)


@app.route("/problemsetting_new", methods=['GET', 'POST'])
@login_required
def create_problem():
    if not current_user.has("make_problems"):
        abort(403)
    if request.method == "GET":
        return render_template("create_problem.html")
    else:
        idx = problemsetting.create_problem(request.form["name"], current_user.id)
        tools.write("建立題目", "preparing_problems", idx, "waiting")
        tools.append(idx + "\n", current_user.folder, "problems")
        return redirect("/problemsetting/" + idx)


@app.route("/problemsetting/<idx>", methods=['GET'])
@login_required
def my_problem_page(idx):
    idx = secure_filename(idx)
    if not current_user.has("make_problems"):
        abort(403)
    if not os.path.isdir("preparing_problems/" + idx) or not os.path.isfile("preparing_problems/" + idx + "/info.json"):
        abort(404)
    if len(os.listdir("preparing_problems/" + idx)) == 0:
        problemsetting.system(f"sudo mount -o loop {idx}.img ./{idx}", "preparing_problems")
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        return render_template("pleasewait.html",
                               action=tools.read("preparing_problems", idx, "waiting"))
    o = problemsetting.check_background_action(idx)
    if o is not None:
        return render_template("pleasewaitlog.html", action=o[1], log=o[0])
    dat = tools.read_json("preparing_problems", idx, "info.json")
    if not current_user.has("admin") and current_user.id not in dat["users"]:
        abort(403)
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
                           langs=executing.langs.keys(), default_interactors=default_interactors)


@app.route("/problemsetting_action", methods=['POST'])
@login_required
def problem_action():
    if not current_user.has("make_problems"):
        abort(403)
    idx = request.form["pid"]
    idx = secure_filename(idx)
    if not os.path.isfile(f"preparing_problems/{idx}/info.json"):
        abort(404)
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        abort(503)
    if problemsetting.check_background_action(idx) is not None:
        abort(503)
    dat = tools.read_json(f"preparing_problems/{idx}/info.json")
    if not current_user.has("admin") and current_user.id not in dat["users"]:
        abort(403)
    return problemsetting.action(request.form)


@app.route("/problemsetting_preview", methods=["GET"])
@login_required
def problem_preview():
    if not current_user.has("make_problems"):
        abort(403)
    idx = request.args["pid"]
    idx = secure_filename(idx)
    if not os.path.isfile(f"preparing_problems/{idx}/info.json"):
        abort(404)
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        return render_template("pleasewait.html", action=tools.read("preparing_problems", idx, "waiting"))
    dat = tools.read_json(f"preparing_problems/{idx}/info.json")
    if not current_user.has("admin") and current_user.id not in dat["users"]:
        abort(403)
    return problemsetting.preview(request.args)


@app.route("/user/<name>", methods=["GET"])
def user_page(name):
    return redirect("/my_submissions")


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("The judge server only supports Linux")
    if not executing.call(["whoami"])[0].startswith("root\n"):
        raise RuntimeError("The judge server must be run as root")
    os.system(f"sudo lxc-start {lxc_name}")
    os.system(f"sudo cp -r -f judge /var/lib/lxc/{lxc_name}/rootfs/")
    tasks.init()
    problemsetting.init()
    app.run(port=8080)


if __name__ == '__main__':
    main()
