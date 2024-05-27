import os

from flask import abort, render_template, redirect, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from modules import tools, server, login, constants, executing, problemsetting, datas

app = server.app


@app.route("/problemsetting", methods=['GET'])
@login_required
def my_problems():
    user = login.check_user("make_problems")
    problem_list = user.data.problems
    problems_dat = []
    for obj in reversed(problem_list):
        idx = obj.pid
        problems_dat.append({"pid": idx, "name": obj.name})
    return render_template("my_problems.html", problems=problems_dat, username=user.id)


@app.route("/problemsetting_new", methods=['GET', 'POST'])
@login_required
def create_problem():
    user = login.check_user("make_problems")
    if request.method == "GET":
        return render_template("create_problem.html")
    else:
        idx = problemsetting.create_problem(request.form["name"], user.data)
        # tools.append(idx + "\n", user.folder, "problems")
        return redirect(f"/problemsetting/{idx}?user={user.id}")


@app.route("/problemsetting/<idx>", methods=['GET'])
@login_required
def my_problem_page(idx):
    idx = secure_filename(idx)
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
    # if not os.path.isdir("preparing_problems/" + idx) or not os.path.isfile("preparing_problems/" + idx +
    # "/info.json"): abort(404) if len(os.listdir("preparing_problems/" + idx)) == 0: problemsetting.system(f"sudo
    # mount -o loop {idx}.img ./{idx}", "preparing_problems")
    o = problemsetting.check_background_action(idx)
    if o is not None:
        return render_template("pleasewaitlog.html", action=o[1], log=o[0])
    dat = pdat.new_data
    user = login.check_user("make_problems", dat["users"])
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
                           versions=problemsetting.query_versions(pdat), enumerate=enumerate,
                           public_files=public_files, default_checkers=default_checkers,
                           langs=executing.langs.keys(), default_interactors=default_interactors,
                           username=user.id,pdat=pdat)


@app.route("/problemsetting_action", methods=['POST'])
@login_required
def problem_action():
    idx = request.form["pid"]
    idx = secure_filename(idx)
    pdat = datas.Problem.query.filter_by(pid=idx).first_or_404()
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        abort(503)
    if problemsetting.check_background_action(idx) is not None:
        abort(503)
    dat = pdat.data
    user = login.check_user("make_problems", dat["users"])
    return problemsetting.action(request.form)


@app.route("/problemsetting_preview", methods=["GET"])
@login_required
def problem_preview():
    idx = request.args["pid"]
    pdat = datas.Problem.query.filter_by(pid=idx).first_or_404()
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        return render_template("pleasewait.html", action=tools.read("preparing_problems", idx, "waiting"))
    dat = pdat.new_data
    user = login.check_user("make_problems", dat["users"])
    return problemsetting.preview(request.args, pdat)
