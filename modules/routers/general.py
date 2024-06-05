import datetime
import json
import os

from flask import abort, render_template, redirect, request, send_file
from flask_login import login_required, current_user
from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter
from werkzeug.utils import secure_filename

from modules import tools, server, constants, executing, tasks, datas

app = server.app

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/problems', methods=['GET'])
def problems():
    public_problems = datas.Problem.query.filter_by(is_public=True)
    problem_cnt = public_problems.count()
    page_cnt = max(1, (problem_cnt - 1) // constants.page_size + 1)
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = public_problems.slice(constants.page_size * (page_idx - 1),
                                     min(problem_cnt, constants.page_size * page_idx)).all()
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("problems.html", problems=got_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


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
        """
        if tools.elapsed(current_user.folder, "submissions") < 5:
            abort(429)
        tools.append(idx + "\n", current_user.folder, "submissions")
        """
        dat = datas.Submission(source="a" + ext, time=datetime.datetime.now(), user=current_user.data,
                               problem=datas.Problem.query.filter_by(pid="test").first(), language=lang,
                               data={"infile": "in.txt", "outfile": "out.txt"}, pid="test")
        datas.add(dat)
        idx = str(dat.id)
        tools.write(code, f"submissions/{idx}/a{ext}")
        tools.write(inp, f"submissions/{idx}/in.txt")
        tasks.submissions_queue.put(idx)
        return redirect("/submission/" + idx)


@app.route("/submit", methods=['POST'])
@login_required
def submit():
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    pid = request.form["pid"]
    pdat = datas.Problem.query.filter_by(pid=pid).first_or_404()
    if lang not in executing.langs:
        abort(404)
    ext = executing.langs[lang].data["source_ext"]
    """
    if tools.elapsed(current_user.folder, "submissions") < 5:
        abort(429)
    tools.append(idx + "\n", current_user.folder, "submissions")
    """
    dat = datas.Submission(source="a" + ext, time=datetime.datetime.now(), user=current_user.data,
                           problem=pdat, language=lang, data={}, pid=pid)
    if "cid" in request.form:
        cdat = datas.Contest.query.filter_by(cid=request.form["cid"]).first_or_404()
        dat.contest = cdat
    datas.add(dat)
    idx = str(dat.id)
    tools.write(code, f"submissions/{idx}/a{ext}")
    tasks.submissions_queue.put(idx)
    return redirect("/submission/" + idx)


@app.route("/submission/<idx>", methods=['GET'])
@login_required
def submission(idx):
    dat: datas.Submission = datas.Submission.query.get_or_404(idx)
    path = "submissions/" + idx
    lang = dat.language
    source = tools.read(path, dat.source)
    source = highlight(source, prepares[executing.langs[lang].name], HtmlFormatter())
    completed = dat.completed
    ce_msg = dat.ce_msg
    ret = ""
    pdat: datas.Problem = dat.problem
    if pdat.pid == "test":
        if not current_user.has("admin") and dat.user_id != current_user.data.id:
            abort(403)
        inp = tools.read_default(path, dat.data["infile"])
        out = tools.read_default(path, dat.data["outfile"])
        result = tools.read_default(path, "results")
        err = tools.read_default(path, "stderr.txt")
        ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                              out=out, completed=completed, result=result, pos=tasks.get_queue_position(idx),
                              ce_msg=ce_msg, je=dat.data.get("JE", False), logid=dat.data.get("log_uuid", ""), err=err)
    else:
        group_results = {}
        problem_info = pdat.data
        if not current_user.has("admin") and dat.user_id != current_user.data.id and current_user.id not in \
                problem_info[
                    "users"]:
            abort(403)
        result = {}
        if completed and not dat.data.get("JE", False):
            result_data = dat.result
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
                              group_results=group_results, pid=pdat.pid, pos=tasks.get_queue_position(idx),
                              ce_msg=ce_msg, je=dat.data.get("JE", False), logid=dat.data.get("log_uuid", ""))
    return ret


@app.route("/problem/<idx>", methods=['GET'])
def problem(idx):
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
    idx = secure_filename(idx)
    path = "problems/" + idx
    dat = pdat.data
    if not pdat.is_public:
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
                           preview=False, samples=enumerate(samples), is_contest=False)


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
    data: datas.User = current_user.data
    submission_obj = data.submissions
    page_size = constants.page_size
    if "pid" in request.args:
        submission_obj = submission_obj.filter_by(pid=request.args.get("pid"))
    submit_cnt = submission_obj.count()
    page_cnt = max(1, (submit_cnt - 1) // page_size + 1)
    out = []
    page = request.args.get("page", "1")
    if not page.isdigit():
        abort(404)
    page_idx = int(page)
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = submission_obj.slice(max(0, submit_cnt - page_size * page_idx),
                                    submit_cnt - page_size * (page_idx - 1)).all()
    for dat in reversed(got_data):
        dat: datas.Submission
        idx = str(dat.id)
        o = {"name": str(dat.id), "time": dat.time, "result": "blank"}
        if not dat.completed:
            o["result"] = "waiting"
        else:
            result = dat.result
            if result and "simple_result" in result:
                o["result"] = result["simple_result"]
        if dat.problem is None:
            continue
        if dat.problem.pid == "test":
            o["source"] = "/test"
            o["source_name"] = "Simple Testing"
        else:
            o["source"] = "/problem/" + dat.problem.pid
            source_dat = dat.problem
            o["source_name"] = source_dat.name
        out.append(o)
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("my_submissions.html", submissions=out, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if not current_user.has("admin"):
        abort(403)
    if request.method == 'GET':
        return render_template("admin.html")
    else:
        abort(404)
