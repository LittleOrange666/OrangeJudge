import os

from flask import abort, render_template, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from modules import tools, server, login, constants, executing, problemsetting, datas

app = server.app


@app.route("/problemsetting", methods=['GET'])
@login_required
def my_problems():
    user = login.check_user("make_problems")
    problem_obj = user.data.problems
    got_data, page_cnt, page_idx, show_pages = tools.pagination(problem_obj)
    problems_dat = []
    for obj in got_data:
        problems_dat.append({"pid": obj.pid, "name": obj.name})
    return render_template("my_problems.html", problems=problems_dat, title="我的題目", page_cnt=page_cnt,
                           page_idx=page_idx, show_pages=show_pages)


@app.route("/problemsetting_all", methods=['GET'])
@login_required
def all_problems():
    login.check_user("admin")
    problem_obj = datas.Problem.query.filter(datas.Problem.pid != "test")
    got_data, page_cnt, page_idx, show_pages = tools.pagination(problem_obj)
    problems_dat = []
    for obj in got_data:
        problems_dat.append({"pid": obj.pid, "name": obj.name})
    return render_template("my_problems.html", problems=problems_dat, title="所有題目", page_cnt=page_cnt,
                           page_idx=page_idx, show_pages=show_pages)


@app.route("/problemsetting_new", methods=['GET', 'POST'])
@login_required
def create_problem():
    user = login.check_user("make_problems")
    if request.method == "GET":
        return render_template("create_problem.html")
    else:
        pid = request.form["pid"]  # 不用加 secure_filename 因為下面那個函數會檢查
        idx = problemsetting.create_problem(request.form["name"], pid, user.data)
        return f"/problemsetting/{idx}", 200


@app.route("/problemsetting/<idx>", methods=['GET'])
@login_required
def my_problem_page(idx):
    idx = secure_filename(idx)
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
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
    action_files = os.listdir(f"preparing_problems/{idx}/actions") if \
        os.path.isdir(f"preparing_problems/{idx}/actions") else []
    actions = []
    for f in action_files:
        if os.path.splitext(f)[1] == ".json":
            actions.append(os.path.splitext(f)[0])
    return render_template("problemsetting.html", dat=constants.default_problem_info | dat, pid=idx,
                           versions=problemsetting.query_versions(pdat), enumerate=enumerate,
                           public_files=public_files, default_checkers=default_checkers,
                           langs=executing.langs.keys(), default_interactors=default_interactors,
                           username=user.id, pdat=pdat, actions=actions)


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
    login.check_user("make_problems", dat["users"])
    return problemsetting.action(request.form)


@app.route("/problemsetting_preview", methods=["GET"])
@server.limiter.limit("30 per 5 second")
@login_required
def problem_preview():
    idx = request.args["pid"]
    pdat = datas.Problem.query.filter_by(pid=idx).first_or_404()
    if os.path.isfile("preparing_problems/" + idx + "/waiting"):
        return render_template("pleasewait.html", action=tools.read("preparing_problems", idx, "waiting"))
    dat = pdat.new_data
    login.check_user("make_problems", dat["users"])
    return problemsetting.preview(request.args, pdat)
