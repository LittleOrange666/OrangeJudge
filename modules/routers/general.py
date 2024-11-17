import datetime
import json

from flask import abort, render_template, redirect, request, jsonify
from flask_login import login_required, current_user
from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter
from werkzeug.utils import secure_filename

from .. import tools, server, constants, executing, tasks, datas, contests, login, config
from ..constants import Permission, problem_path
from ..constants import submission_path
from ..server import sending_file

app = server.app

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/problems', methods=['GET'])
def problems():
    public_problems = datas.Problem.query.filter_by(is_public=True)
    got_data, page_cnt, page_idx, show_pages = tools.pagination(public_problems, False)
    return render_template("problems.html", problems=got_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=show_pages)


@app.route('/test', methods=['GET'])
@login_required
def test():
    return render_template("test.html", langs=executing.langs.keys())


@app.route('/test_submit', methods=['POST'])
@server.limiter.limit(config.judge.limit)
@login_required
def test_submit():
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    inp = request.form["input"]
    if not inp.endswith("\n"):
        inp += "\n"
    if lang not in executing.langs:
        abort(404)
    ext = executing.langs[lang].data["source_ext"]
    fn = constants.source_file_name + ext
    dat = datas.Submission(source=fn, time=datetime.datetime.now(), user=current_user.data,
                           problem=datas.Problem.query.filter_by(pid="test").first(), language=lang,
                           data={"infile": "in.txt", "outfile": "out.txt"}, pid="test", simple_result="waiting",
                           queue_position=0)
    datas.add(dat)
    idx = str(dat.id)
    tools.write(code, dat.path / fn)
    tools.write(inp, dat.path / "in.txt")
    dat.queue_position = tasks.enqueue(dat.id)
    datas.add(dat)
    return "/submission/" + idx, 200


@app.route("/submit", methods=['POST'])
@server.limiter.limit(config.judge.limit)
@login_required
def submit():
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    if len(code) > config.judge.file_size * 1024:
        abort(400)
    pid = request.form["pid"]
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=pid).first_or_404()
    if lang not in executing.langs:
        abort(404)
    if not pdat.lang_allowed(lang):
        abort(400)
    ext = executing.langs[lang].data["source_ext"]
    fn = constants.source_file_name + ext
    dat = datas.Submission(source=fn, time=datetime.datetime.now(), user=current_user.data,
                           problem=pdat, language=lang, data={}, pid=pid, simple_result="waiting",
                           queue_position=0)
    if "cid" in request.form:
        cdat: datas.Contest = datas.Contest.query.filter_by(cid=request.form["cid"]).first_or_404()
        contests.check_access(cdat)
        per_id = contests.check_period(cdat)
        dat.contest = cdat
        if per_id:
            dat.period_id = per_id
            if cdat.data["pretest"] != "no":
                dat.just_pretest = True
    datas.add(dat)
    idx = str(dat.id)
    tools.write(code, dat.path / fn)
    dat.queue_position = tasks.enqueue(dat.id)
    datas.add(dat)
    return "/submission/" + idx


@app.route("/submission/<idx>", methods=['GET'])
@login_required
def submission(idx: str):
    dat: datas.Submission = datas.Submission.query.get_or_404(idx)
    lang = dat.language
    source = tools.read(dat.path / dat.source)
    source = highlight(source, prepares[executing.langs.get(lang, executing.langs["PlainText"]).name], HtmlFormatter())
    completed = dat.completed
    ce_msg = dat.ce_msg
    pdat: datas.Problem = dat.problem
    if pdat.pid == "test":
        if not current_user.has(Permission.admin) and dat.user_id != current_user.data.id:
            abort(403)
        inp = tools.read_default(dat.path / dat.data["infile"])
        out = tools.read_default(dat.path / dat.data["outfile"])
        result = dat.simple_result or "unknown"
        err = tools.read_default(dat.path / "stderr.txt")
        ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                              out=out, completed=completed, result=result, pos=tasks.get_queue_position(dat),
                              ce_msg=ce_msg, je=dat.data.get("JE", False), logid=dat.data.get("log_uuid", ""), err=err)
    else:
        group_results = {}
        protected = True
        checker_protected = True
        problem_info = pdat.data
        if not current_user.has(Permission.admin) and dat.user_id != current_user.data.id and current_user.id not in \
                problem_info[
                    "users"]:
            abort(403)
        super_access = current_user.has(Permission.admin) or current_user.id in problem_info["users"]
        result = {}
        see_cc = False
        if completed and not dat.data.get("JE", False) and dat.result is not None:
            result_data = dat.result
            result["CE"] = result_data["CE"]
            results = result_data["results"]
            result["protected"] = protected = ((not problem_info.get('public_testcase', False) or bool(dat.period_id))
                                               and not super_access)
            checker_protected = ((not problem_info.get('public_checker', False) or bool(dat.period_id))
                                 and not super_access)
            result["checker_protected"] = checker_protected
            testcase_path = dat.path / "testcases"
            for i in range(len(results)):
                if results[i]["result"] != "SKIP" and (not protected or super_access or results[i]["sample"]):
                    results[i]["in"] = tools.read(testcase_path / f"{i}.in")
                    results[i]["out"] = tools.read(testcase_path / f"{i}.ans")
                else:
                    results[i]["in"] = results[i]["out"] = ""
                if results[i].get("has_output", False):
                    results[i]["user_out"] = tools.read(testcase_path / f"{i}.out")
            result["results"] = results
            if "group_results" in result_data:
                gpr = result_data["group_results"]
                if len(gpr) > 0 and type(next(iter(gpr.values()))) == dict:
                    group_results = gpr
                    for o in group_results.values():
                        o["class"] = constants.result_class.get(o["result"], "")
            if "total_score" in result_data:
                result["total_score"] = result_data["total_score"]
            cc_mode = problem_info.get("codechecker_mode", "disabled")
            see_cc = cc_mode == "public" or cc_mode == "private" and super_access
        cc = ""
        if see_cc:
            cc = tools.read(dat.path / "codechecker_result.txt")
        link = f"/problem/{pdat.pid}"
        contest = None
        cid = None
        if dat.contest_id:
            cdat: datas.Contest = dat.contest
            contest = cdat.name
            cid = cdat.cid
            for k, v in cdat.data["problems"].items():
                if v["pid"] == pdat.pid:
                    link = f"/contest/{cdat.cid}/problem/{k}"
                    break
        ret = render_template("submission/problem.html", lang=lang, source=source, completed=completed,
                              pname=problem_info["name"], result=result, enumerate=enumerate,
                              group_results=group_results, link=link, pos=tasks.get_queue_position(dat),
                              ce_msg=ce_msg, je=dat.data.get("JE", False), logid=dat.data.get("log_uuid", ""),
                              super_access=super_access, contest=contest, cid=cid, protected=protected,
                              checker_protected=checker_protected, see_cc=see_cc, cc=cc)
    return ret


@app.route("/problem/<idx>", methods=['GET'])
def problem_page(idx):
    if idx == "test":
        return redirect("/test")
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
    idx = secure_filename(idx)
    dat = pdat.data
    if not pdat.is_public:
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.has(Permission.admin) and current_user.id not in dat.get("users", []):
            abort(403)
    langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
    return render_problem(dat, idx, langs, is_contest=False)


def render_problem(dat, idx: str, langs: list[str], **kwargs):
    path = problem_path / idx
    statement = tools.read(path / "statement.html")
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = dat.get("manual_samples", []) + [[tools.read(path / k / o["in"]), tools.read(path / k / o["out"])]
                                               for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if
                                               o.get("sample", False)]
    return render_template("problem.html", dat=dat, statement=statement,
                           langs=langs, lang_exts=lang_exts, pid=idx,
                           preview=False, samples=enumerate(samples), **kwargs)


@app.route("/problem_file/<idx>/<filename>", methods=['GET'])
@server.limiter.limit(config.server.file_limit)
def problem_file(idx, filename):
    idx = secure_filename(idx)
    filename = secure_filename(filename)
    if "cid" in request.args:
        cdat: datas.Contest = datas.Contest.query.filter_by(cid=request.args["cid"]).first_or_404()
        for obj in cdat.data["problems"].values():
            if obj["pid"] == idx:
                break
        else:
            abort(404)
        contests.check_access(cdat)
    else:
        pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
        dat = pdat.data
        if not pdat.is_public:
            if not current_user.is_authenticated:
                abort(403)
            if not current_user.has(Permission.admin) and current_user.id not in dat["users"]:
                abort(403)
    target = problem_path / idx / "public_file" / filename
    return sending_file(target)


@app.route("/status", methods=["GET"])
def all_status():
    return render_template("status.html")


@app.route("/status_data", methods=["POST"])
def all_status_data():
    status = datas.Submission.query.filter_by(contest_id=None)
    if "user" in request.form and len(request.form["user"]):
        users = datas.User.query.filter_by(username=request.form["user"])
        if users.count() == 0:
            status = status.filter_by(id=-1)
        else:
            user: datas.User = users.first()
            status = status.filter_by(user=user)
    if "pid" in request.form and len(request.form["pid"]):
        status = status.filter_by(pid=request.form["pid"])
    got_data, page_cnt, page_idx, show_pages = tools.pagination(status)
    out = []
    for obj in got_data:
        obj: datas.Submission
        pid = obj.pid
        problem = datas.Problem.query.filter_by(pid=pid)
        problem_name = problem.first().name if problem.count() else "unknown"
        result = obj.simple_result or "unknown"
        can_see = current_user.is_authenticated and (current_user.has(Permission.admin) or
                                                     current_user.id == obj.user.username or
                                                     (obj.problem.user and
                                                      obj.problem.user.username == current_user.id))
        out.append({"idx": str(obj.id),
                    "time": obj.time.timestamp(),
                    "user_id": obj.user.username,
                    "user_name": obj.user.display_name,
                    "problem": pid,
                    "problem_name": problem_name,
                    "lang": obj.language,
                    "result": result,
                    "can_see": can_see})
    ret = {"show_pages": show_pages, "page_cnt": page_cnt, "page": page_idx, "data": out}
    return jsonify(ret)


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.has(Permission.admin):
        abort(403)
    if request.method == 'GET':
        users = datas.User.query.all()
        return render_template("admin.html", users=users)
    else:
        if request.form["action"] == "update_user":
            user: datas.User = datas.User.query.filter_by(username=request.form["username"]).first_or_404()
            user.display_name = request.form["display_name"]
            if len(request.form["password"]) > 1:
                user.password_sha256_hex = login.try_hash(request.form["password"])
            perms = user.permission_list()
            new_perms = request.form["permissions"].split(";")
            for perm_name in ("admin", "make_problems"):
                if perm_name in new_perms:
                    if perm_name not in perms:
                        perms.append(perm_name)
                else:
                    if perm_name in perms:
                        perms.remove(perm_name)
            user.permissions = ";".join(perms)
            datas.add(user)
            return "OK", 200
        abort(404)


@app.route('/preferences', methods=['GET'])
def preferences():
    return render_template("preferences.html")
