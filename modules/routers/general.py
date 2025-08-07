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
import datetime
import json

from flask import abort, render_template, redirect, request, jsonify
from flask_login import login_required, current_user
from pygments import highlight, lexers
from pygments.formatters import HtmlFormatter
from werkzeug.utils import secure_filename

from .. import tools, server, constants, executing, tasks, datas, contests, config, objs, submitting
from ..constants import problem_path, preparing_problem_path
from ..objs import Permission
from ..server import sending_file

app = server.app

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}

submit_limit = server.limiter.shared_limit(config.judge.limit, "submit_limit")


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route('/problems', methods=['GET'])
def problems():
    public_problems = datas.filter_by(datas.Problem, is_public=True)
    got_data, page_cnt, page_idx, show_pages = tools.pagination(public_problems, False)
    return render_template("problems.html", problems=got_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=show_pages)


@app.route('/test', methods=['GET'])
@login_required
def test():
    return render_template("test.html", langs=executing.langs.keys())


@app.route('/test_submit', methods=['POST'])
@submit_limit
@login_required
def test_submit():
    if datas.count(datas.Submission, user=current_user.data, completed=False) >= config.judge.pending_limit:
        return "Too many uncompleted submissions", 409
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    inp = request.form["input"]
    idx = submitting.test_submit(lang, code, inp, current_user)
    return "/submission/" + idx, 200


@app.route("/submit", methods=['POST'])
@submit_limit
@login_required
def submit():
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    pid = request.form["pid"]
    cid = request.form.get("cid")
    idx = submitting.submit(lang, pid, code, cid, current_user)
    return "/submission/" + idx


@app.route("/submission/<idx>", methods=['GET'])
@login_required
def submission(idx: str):
    int_idx = tools.to_int(idx)
    dat: datas.Submission = datas.get_or_404(datas.Submission, int_idx)
    lang = dat.language
    source = tools.read(dat.path / dat.source)
    source = highlight(source, prepares[executing.langs.get(lang, executing.langs["PlainText"]).name], HtmlFormatter())
    completed = dat.completed
    ce_msg = dat.ce_msg
    pdat: datas.Problem = dat.problem
    submit_info = dat.datas
    if pdat.pid == "test":
        if not current_user.has(Permission.admin) and dat.user_id != current_user.data.id:
            abort(403)
        info = dat.datas
        inp = tools.read_default(dat.path / info.infile)
        out = tools.read_default(dat.path / info.outfile)
        result = dat.simple_result or "unknown"
        err = tools.read_default(dat.path / "stderr.txt")
        ret = render_template("submission/test.html", lang=lang, source=source, inp=inp,
                              out=out, completed=completed, result=result, pos=tasks.get_queue_position(dat),
                              ce_msg=ce_msg, je=info.JE, logid=info.log_uuid, err=err)
    else:
        group_results = {}
        protected = True
        checker_protected = True
        problem_info = pdat.datas
        if not current_user.has(Permission.admin) and dat.user_id != current_user.data.id and current_user.id not in \
                problem_info.users:
            abort(403)
        ac_info = ""
        super_access = current_user.has(Permission.admin) or current_user.id in problem_info.users
        result = {}
        see_cc = False
        testcase_path = dat.path / "testcases"
        result_data = dat.results
        results = result_data.results
        if ("AC" in dat.simple_result and dat.completed and result_data.total_score >= problem_info.top_score and
                not dat.just_pretest):
            ac_info = problem_info.ac_info
        if completed and not submit_info.JE:
            result["CE"] = result_data.CE
            result["protected"] = protected = ((not problem_info.public_testcase or bool(dat.period_id))
                                               and not super_access)
            checker_protected = ((not problem_info.public_checker or bool(dat.period_id))
                                 and not super_access)
            result["checker_protected"] = checker_protected
            for i in range(len(results)):
                if (results[i].result not in (objs.TaskResult.SKIP, objs.TaskResult.PASS)
                        and (not protected or super_access or results[i].sample)):
                    results[i].in_txt = tools.read_default(testcase_path / f"{i}.in")
                    results[i].ans_txt = tools.read_default(testcase_path / f"{i}.ans")
                else:
                    results[i].in_txt = results[i].ans_txt = ""
                if results[i].has_output:
                    results[i].out_txt = tools.read_default(testcase_path / f"{i}.out")
            gpr = result_data.group_results
            if len(gpr) > 0 and type(next(iter(gpr.values()))) is objs.GroupResult:
                group_results = gpr
            result["total_score"] = result_data.total_score
            cc_mode = problem_info.codechecker_mode
            see_cc = cc_mode == objs.CodecheckerMode.public or cc_mode == objs.CodecheckerMode.private and super_access
        cc = ""
        if see_cc:
            cc = tools.read_default(dat.path / "codechecker_result.txt", default="INFO NOT FOUND")
        link = f"/problem/{pdat.pid}"
        contest = None
        cid = None
        if dat.contest_id:
            cdat: datas.Contest = dat.contest
            contest = cdat.name
            cid = cdat.cid
            for k, v in cdat.datas.problems.items():
                if v.pid == pdat.pid:
                    link = f"/contest/{cdat.cid}/problem/{k}"
                    break
        ret = render_template("submission/problem.html", lang=lang, source=source, completed=completed,
                              pname=problem_info.name, result=result, enumerate=enumerate,
                              group_results=group_results, link=link, pos=tasks.get_queue_position(dat),
                              ce_msg=ce_msg, je=submit_info.JE, logid=submit_info.log_uuid,
                              super_access=super_access, contest=contest, cid=cid, protected=protected,
                              checker_protected=checker_protected, see_cc=see_cc, cc=cc, results=results,
                              ac_info=ac_info)
    return ret


@app.route("/problem/<idx>", methods=['GET'])
def problem_page(idx):
    if idx == "test":
        return redirect("/test")
    pdat = datas.first_or_404(datas.Problem, pid=idx)
    idx = secure_filename(idx)
    dat = pdat.datas
    if not pdat.is_public:
        if not current_user.is_authenticated:
            abort(403)
        if not current_user.has(Permission.admin) and current_user.id not in dat.users:
            abort(403)
    langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
    default_code = dat.default_code
    files = [f for f in default_code.values() if f and f.strip()]
    content_map = {}
    for f in files:
        content_map[f] = (pdat.path / "file" / f).open(encoding="utf-8").read()
    default_code = {k: content_map.get(v,"") for k, v in default_code.items()}
    return render_problem(dat, idx, langs, is_contest=False, default_code=default_code)


def render_problem(dat: objs.ProblemInfo, idx: str, langs: list[str], preview: bool = False, **kwargs):
    if preview:
        path = preparing_problem_path / idx
    else:
        path = problem_path / idx
    statement = tools.read(path / "statement.html")
    lang_exts = json.dumps({k: v.source_ext for k, v in executing.langs.items()})
    samples = dat.manual_samples
    samples.extend([objs.ManualSample(tools.read(path / "testcases" / o.in_file),
                                      tools.read(path / "testcases" / o.out_file))
                    for o in dat.testcases if o.sample])
    samples.extend([objs.ManualSample(tools.read(path / "testcases_gen" / o.in_file),
                                      tools.read(path / "testcases_gen" / o.out_file))
                    for o in dat.testcases_gen if o.sample])
    return render_template("problem.html", dat=dat, statement=statement,
                           langs=langs, lang_exts=lang_exts, pid=idx,
                           preview=preview, samples=enumerate(samples), **kwargs)


@app.route("/problem_file/<idx>/<filename>", methods=['GET'])
@server.limiter.limit(config.server.file_limit)
def problem_file(idx, filename):
    idx = secure_filename(idx)
    filename = secure_filename(filename)
    if "cid" in request.args:
        cdat = datas.first_or_404(datas.Contest, cid=request.args["cid"])
        for obj in cdat.datas.problems.values():
            if obj.pid == idx:
                break
        else:
            abort(404)
        contests.check_access(cdat)
    else:
        pdat = datas.first_or_404(datas.Problem, pid=idx)
        dat = pdat.datas
        if not pdat.is_public:
            if not current_user.is_authenticated:
                abort(403)
            if not current_user.has(Permission.admin) and current_user.id not in dat.users:
                abort(403)
    target = problem_path / idx / "public_file" / filename
    return sending_file(target)


@app.route("/status", methods=["GET"])
def all_status():
    return render_template("status.html", languages=sorted(executing.langs.keys()),
                           can_filter_results=constants.can_filter_results, can_edit=current_user.has(Permission.admin))


@app.route("/status_data", methods=["POST"])
def all_status_data():
    status = datas.filter_by(datas.Submission, contest_id=None)
    if "user" in request.form and len(request.form["user"]):
        users = datas.filter_by(datas.User, username=request.form["user"])
        if users.count() == 0:
            status = status.filter_by(id=-1)
        else:
            user: datas.User = users.first()
            status = status.filter_by(user=user)
    if "pid" in request.form and len(request.form["pid"]):
        status = status.filter_by(pid=request.form["pid"])
    if "result" in request.form and request.form["result"] in objs.TaskResult.__members__:
        result = objs.TaskResult[request.form["result"]]
        status = status.filter_by(simple_result_flag=result.name)
    if "lang" in request.form and request.form["lang"] in executing.langs:
        status = status.filter_by(language=request.form["lang"])
    got_data, page_cnt, page_idx, show_pages = tools.pagination(status)
    out = []
    for obj in got_data:
        obj: datas.Submission
        pid = obj.pid
        problem = datas.filter_by(datas.Problem, pid=pid)
        problem_name = problem.first().name if problem.count() else "unknown"
        result = obj.simple_result or "unknown"
        can_see = current_user.is_authenticated and (current_user.has(Permission.admin) or
                                                     current_user.id == obj.user.username or
                                                     (obj.problem.user and
                                                      obj.problem.user.username == current_user.id))
        can_rejudge = can_see and (current_user.has(Permission.admin) or obj.problem.user.username == current_user.id)
        out.append({"idx": str(obj.id),
                    "time": obj.time.timestamp(),
                    "user_id": obj.user.username,
                    "user_name": obj.user.display_name,
                    "problem": pid,
                    "problem_name": problem_name,
                    "lang": obj.language,
                    "result": result,
                    "can_see": can_see,
                    "can_rejudge": can_rejudge})
    ret = {"show_pages": show_pages, "page_cnt": page_cnt, "page": page_idx, "data": out}
    return jsonify(ret)


@app.route('/preferences', methods=['GET'])
def preferences():
    return render_template("preferences.html")


@app.route('/rejudge', methods=['POST'])
@login_required
def rejudge():
    idx = request.form["idx"]
    dat = datas.get_or_404(datas.Submission, tools.to_int(idx))
    if "cid" in request.form:
        if dat.contest.cid != request.form["cid"]:
            abort(400)
        cdat: datas.Contest = datas.first_or_404(datas.Contest.query, cid=request.form["cid"])
        if not contests.check_super_access(cdat):
            abort(403)
    else:
        if dat.contest_id is not None:
            abort(400)
        if not current_user.has(Permission.admin) and current_user.id != dat.problem.user.username:
            abort(403)
    if not dat.completed:
        abort(400)
    tasks.rejudge(dat, "wait for rejudge")
    datas.add(dat)
    return "OK", 200


@app.route('/rejudge_all', methods=['POST'])
@login_required
def rejudge_all():
    if "pid" not in request.form or request.form["pid"] == "":
        return "僅允許Rejudge特定題目", 400
    pid = request.form["pid"]
    if "cid" in request.form:
        cdat: datas.Contest = datas.first_or_404(datas.Contest.query, cid=request.form["cid"])
        if not contests.check_super_access(cdat):
            abort(403)
        probs = cdat.datas.problems
        if pid not in probs:
            abort(404)
        the_pid = probs[pid].pid
        prob = datas.first_or_404(datas.Problem, pid=the_pid)
        status = datas.filter_by(datas.Submission, problem_id=prob.id, contest_id=cdat.id, completed=True)
    else:
        if pid == "test":
            return "不允許Rejudge測試題目", 400
        prob = datas.first_or_404(datas.Problem, pid=pid)
        if not current_user.has(Permission.admin) and current_user.id != prob.user.username:
            abort(403)
        status = datas.filter_by(datas.Submission, problem_id=prob.id, contest_id=None, completed=True)
    if "result" in request.form and request.form["result"] in objs.TaskResult.__members__:
        result = objs.TaskResult[request.form["result"]]
        status = status.filter_by(simple_result_flag=result.name)
    if "lang" in request.form and request.form["lang"] in executing.langs:
        status = status.filter_by(language=request.form["lang"])
    for a_submit in status:
        tasks.rejudge(a_submit, "wait for rejudge")
        datas.add(a_submit)
    return "OK", 200


@app.route('/about_judge', methods=['GET'])
def about_judge():
    out = []
    for lang in executing.langs.values():
        out.append({"name": lang.branch, "compile": " ".join(lang.sample_compile_cmd),
                    "run": " ".join(lang.sample_exec_cmd)})
    return render_template("about_judge.html", langs=out)
