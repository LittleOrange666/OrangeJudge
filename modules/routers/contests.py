import json
from datetime import datetime, timedelta

from flask import abort, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm.attributes import flag_modified

from modules import server, login, constants, contests, datas, tools, executing

app = server.app


@app.route("/contests", methods=["GET"])
def contests_list():
    public_contests = datas.Contest.query
    contest_cnt = public_contests.count()
    page_cnt = max(1, (contest_cnt - 1) // constants.page_size + 1)
    page_idx = tools.to_int(request.args.get("page", "1"))
    if page_idx <= 0 or page_idx > page_cnt:
        abort(404)
    got_data = public_contests.slice(constants.page_size * (page_idx - 1),
                                     min(contest_cnt, constants.page_size * page_idx)).all()
    displays = [1, page_cnt]
    displays.extend(range(max(2, page_idx - 2), min(page_cnt, page_idx + 2) + 1))
    return render_template("contests.html", contests=got_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=sorted(set(displays)))


@app.route("/create_contest", methods=["POST"])
@login_required
def create_contest():
    login.check_user("make_problems")
    name = request.form.get("contest_name")
    if not name or len(name) > 120:
        abort(400)
    idx = contests.create_contest(name, current_user.data)
    return "/contest/" + idx, 200


@app.route("/contest/<idx>", methods=["GET"])
def contest_page(idx):
    dat: datas.Contest = datas.Contest.query.filter_by(cid=idx).first_or_404()
    contests.check_access(dat)
    info = dat.data
    can_edit = current_user.is_authenticated and current_user.id in info["users"]
    return render_template("contest.html", cid=idx, data=info, can_edit=can_edit)


@app.route("/contest/<cid>/problem/<pid>", methods=["GET"])
def contest_problem(cid, pid):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    contests.check_access(cdat)
    info = cdat.data
    idx = ""
    if pid not in info["problems"]:
        abort(404)
    idx = info["problems"][pid]["pid"]
    pdat: datas.Problem = datas.Problem.query.filter_by(pid=idx).first_or_404()
    path = "problems/" + idx
    dat = pdat.data
    statement = tools.read(path, "statement.html")
    lang_exts = json.dumps({k: v.data["source_ext"] for k, v in executing.langs.items()})
    samples = dat.get("manual_samples", []) + [[tools.read(path, k, o["in"]), tools.read(path, k, o["out"])]
                                               for k in ("testcases", "testcases_gen") for o in dat.get(k, []) if
                                               o.get("sample", False)]
    return render_template("problem.html", dat=dat, statement=statement,
                           langs=executing.langs.keys(), lang_exts=lang_exts, pid=idx,
                           preview=False, samples=enumerate(samples), is_contest=True, cid=cid,
                           cname=cdat.name, pidx=pid)


@app.route("/contest/<cid>/status/<page_str>", methods=["POST"])
def contest_status(cid, page_str):
    dat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    page = tools.to_int(page_str)
    page_size = constants.page_size
    status = dat.submissions
    if "user" in request.form:
        user: datas.User = datas.User.query.filter_by(username=request.form["user"]).first_or_404()
        status = status.filter_by(user=user)
    status_count = status.count()
    page_cnt = max(1, (status_count - 1) // page_size + 1)
    if page <= 0 or page > page_cnt:
        abort(404)
    got_data: list[datas.Submission] = status.slice(page_size * (page - 1),
                                                    min(status_count, constants.page_size * page)).all()
    displays = [1, page_cnt]
    displays.extend(range(max(2, page - 2), min(page_cnt, page + 2) + 1))
    displays = sorted(set(displays))
    out = []
    for obj in reversed(got_data):
        pid = obj.pid
        problem = "?"
        problem_name = "?"
        for k, v in dat.data["problems"].items():
            if v["pid"] == pid:
                problem = k
                problem_name = v["name"]
        result = "blank"
        if not obj.completed:
            result = "waiting"
        else:
            res = obj.result
            if res and "simple_result" in res:
                result = res["simple_result"]
        out.append({"idx": str(obj.id),
                    "time": obj.time,
                    "user_id": obj.user.username,
                    "user_name": obj.user.display_name,
                    "problem": problem,
                    "problem_name": problem_name,
                    "lang": obj.language,
                    "result": result})
    ret = {"show_pages": displays, "page_cnt": page_cnt, "page": page, "data": out}
    return jsonify(ret)


@app.route("/contest_action", methods=['POST'])
@login_required
def contest_action():
    idx = request.form["cid"]
    cdat = datas.Contest.query.filter_by(cid=idx).first_or_404()
    if not current_user.id in cdat.data["users"]:
        abort(403)
    return contests.action(request.form, cdat)


@app.route("/contest/<cid>/register", methods=['POST'])
@login_required
def contest_register(cid):
    dat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    if not dat.data["can_register"]:
        abort(403)
    if current_user.id in dat.data["participants"]:
        abort(409)
    dat.data["participants"].append(current_user.id)
    flag_modified(dat, "data")
    datas.add(dat)
    return "OK", 200


@app.route("/contest/<cid>/unregister", methods=['POST'])
@login_required
def contest_unregister(cid):
    dat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    if not dat.data["can_register"]:
        abort(403)
    if current_user.id not in dat.data["participants"]:
        abort(409)
    dat.data["participants"].remove(current_user.id)
    flag_modified(dat, "data")
    datas.add(dat)
    return "OK", 200


@app.route("/contest/<cid>/virtual", methods=['GET', 'POST'])
@login_required
def virtual_register(cid):
    dat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    if not dat.can_virtual():
        abort(403)
    if current_user.id in dat.data["virtual_participants"]:
        abort(409)
    if request.method == "GET":
        return render_template("virtual_register.html", cid=cid, name=dat.name)
    else:
        start_time: datetime
        try:
            start_time = datetime.fromisoformat(request.form["start_time"])
            per = datas.Period.query.filter_by(start_time=start_time, contest=dat)
            idx = 0
            if per.count():
                idx = per.first().id
            else:
                nw_per = datas.Period(start_time=start_time,
                                      end_time=start_time + timedelta(minutes=dat.data["elapsed"]),
                                      contest=dat)
                datas.add(nw_per)
                idx = nw_per.id
            dat.data["virtual_participants"][current_user.id] = idx
            flag_modified(dat, "data")
            datas.add(dat)
        except ValueError:
            abort(400)
        return "OK", 200


@app.route("/contest/<cid>/standing", methods=['GET', 'POST'])
def contest_standing(cid):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    per: datas.Period = datas.Period.query.get_or_404(cdat.main_period_id)
    ret = []
    mp = {}
    rmp = {}
    for k, v in cdat.data["problems"].items():
        rmp[v["pid"]] = k
    for dat in per.submissions:
        dat: datas.Submission
        if dat.completed and "group_results" in dat.result:
            if dat.user_id not in mp:
                mp[dat.user_id] = dat.user.display_name
            scores = {k: v["gainscore"] for k, v in dat.result["group_results"].items()}
            ret.append({"user": mp[dat.user_id],
                        "pid": rmp[dat.pid],
                        "scores": scores,
                        "total_score": dat.result["total_score"],
                        "time": dat.time.timestamp()})
    return jsonify({"submissions": ret,
                    "start_time": per.start_time.timestamp(),
                    "rule": cdat.data["type"],
                    "pids": list(cdat.data["problems"].keys())})
