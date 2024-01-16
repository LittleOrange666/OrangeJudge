import json
import os.path
import sys

from flask import Flask, render_template, request, redirect, session, abort, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from modules import executing, tasks, tools, problemsetting, constants
from modules.login import try_login, init_login
from modules.constants import result_class, lxc_name

from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}
app = Flask(__name__, static_url_path='/static', static_folder="static/", template_folder="templates/")
app.secret_key = 'HP4xkCix2nf5qCmxSXV0sBwocE2CjECC5z2T9TKQmv8'
init_login(app)


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    nxt = request.form.get('next')
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(nxt or '/')
        return render_template("login.html")
    name = request.form['user_id']
    user = try_login(name, request.form['password'])
    if user is not None:
        login_user(user)
        print(user)
        return redirect(nxt or '/')
    return redirect('/login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/problems', methods=['GET'])
def problems():
    return render_template("problems.html", problems=json.load(open("data/public_problems.json")))


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
        source = f"submissions/{idx}/a{ext}"
        with open(source, "w") as f:
            f.write(code)
        infile = f"submissions/{idx}/in.txt"
        with open(infile, "w") as f:
            f.write(inp)
        dat = {"type": "test", "source": "a" + ext, "infile": "in.txt", "outfile": "out.txt", "lang": lang,
               "user": current_user.id, "time": tools.get_timestring()}
        with open(f"submissions/{idx}/info.json", "w", encoding="utf8") as f:
            json.dump(dat, f)
        with open(current_user.folder + "submissions", "a") as f:
            f.write(idx + "\n")
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
    source = f"submissions/{idx}/a{ext}"
    with open(source, "w") as f:
        f.write(code)
    dat = {"type": "problem", "source": "a" + ext, "lang": lang, "pid": pid, "user": current_user.id,
           "time": tools.get_timestring()}
    with open(f"submissions/{idx}/info.json", "w", encoding="utf8") as f:
        json.dump(dat, f)
    with open(current_user.folder + "submissions", "a") as f:
        f.write(idx + "\n")
    tasks.submissions_queue.put(idx)
    return redirect("/submission/" + idx)


@app.route("/submission/<idx>", methods=['GET'])
@login_required
def submission(idx):
    idx = secure_filename(idx)
    path = "submissions/" + idx
    if not os.path.isdir(path):
        abort(404)
    with open(path + "/info.json") as f:
        dat = json.load(f)
    if not current_user.has("admin") and dat["user"] != current_user.id:
        abort(403)
    lang = dat["lang"]
    with open(path + "/" + dat["source"]) as f:
        source = f.read()
    source = highlight(source, prepares[executing.langs[lang].name], HtmlFormatter())
    completed = os.path.exists(path + "/completed")
    ce_msg = ""
    if os.path.exists(path + "/ce_msg.txt"):
        with open(path + "/ce_msg.txt") as f:
            ce_msg = f.read()
    match dat["type"]:
        case "test":
            with open(path + "/" + dat["infile"]) as f:
                inp = f.read()
            out = ""
            result = ""
            if os.path.exists(path + "/result"):
                with open(path + "/result") as f:
                    result = f.read()
                if result.startswith("OK"):
                    with open(path + "/" + dat["outfile"]) as f:
                        out = f.read()
            ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                                  out=out, completed=completed, result=result, pos=tasks.get_queue_position(idx),
                                  ce_msg=ce_msg)
        case "problem":
            pid = dat["pid"]
            problem_path = f"problems/{pid}/"
            group_results = {}
            with open(problem_path + "info.json") as f:
                problem_info = json.load(f)
            result = {}
            if completed:
                with open(path + "/results.json") as f:
                    result_data = json.load(f)
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
        return open(path + "/rendered.html").read()
    with open(path + "/info.json") as f:
        dat = json.load(f)
    with open(path + "/statement.html") as f:
        statement = f.read()
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
               for k in ("testcases", "testcases_gen") for o in dat[k] if o.get("sample", False)]
    ret = render_template("problem.html", dat=dat, statement=statement,
                          langs=executing.langs.keys(), lang_exts=lang_exts, pid=idx,
                          preview=False, samples=enumerate(samples))
    with open(path + "/rendered.html", "w") as f:
        f.write(ret)
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
    with open(current_user.folder + "submissions") as f:
        submission_list = f.read().split()
    out = []
    for idx in reversed(submission_list):
        o = {"name": idx, "time": "blank", "result": "blank"}
        if not tools.exists(f"submissions/{idx}/info.json"):
            continue
        with open(f"submissions/{idx}/info.json") as f:
            dat = json.load(f)
        if "time" in dat:
            o["time"] = dat["time"]
        if not os.path.isfile(f"submissions/{idx}/results.json"):
            o["result"] = "waiting"
        else:
            with open(f"submissions/{idx}/results.json") as f:
                result = json.load(f)
            if "simple_result" in result:
                o["result"] = result["simple_result"]
        if dat["type"] == "test":
            o["source"] = "/test"
            o["source_name"] = "Simple Testing"
        else:
            o["source"] = "/problem/" + dat["pid"]
            with open(f"problems/{dat['pid']}/info.json") as f:
                source_dat = json.load(f)
            o["source_name"] = source_dat["name"]
        out.append(o)
    return render_template("my_submissions.html", submissions=out)


@app.route("/problemsetting", methods=['GET'])
@login_required
def my_problems():
    if not current_user.has("make_problems"):
        abort(403)
    with open(current_user.folder + "/problems") as f:
        problem_list = f.read().split()
    problems_dat = []
    for idx in reversed(problem_list):
        if os.path.isfile(f"preparing_problems/{idx}.img") and not os.path.isfile(
                f"preparing_problems/{idx}/info.json"):
            problemsetting.system(f"sudo mount -o loop {idx}.img ./{idx}", "preparing_problems")
        with open(f"preparing_problems/{idx}/info.json") as f:
            dat = json.load(f)
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
        with open("preparing_problems/" + idx + "/waiting", "w") as f:
            f.write("建立題目")
        with open(current_user.folder + "/problems", "a") as f:
            f.write(idx + "\n")
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
        return render_template("pleasewait.html", action=open("preparing_problems/" + idx + "/waiting").read())
    o = problemsetting.check_background_action(idx)
    if o is not None:
        return render_template("pleasewaitlog.html", action=o[1], log=o[0])
    with open("preparing_problems/" + idx + "/info.json") as f:
        dat = json.load(f)
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
        with open("preparing_problems/" + idx + "/info.json", "w") as f:
            json.dump(dat, f, indent=2)
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
    with open(f"preparing_problems/{idx}/info.json") as f:
        dat = json.load(f)
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
        return render_template("pleasewait.html", action=open("preparing_problems/" + idx + "/waiting").read())
    with open(f"preparing_problems/{idx}/info.json") as f:
        dat = json.load(f)
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
