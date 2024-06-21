import json
import time
from datetime import datetime, timedelta

from flask import abort, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm.attributes import flag_modified

from modules import server, login, contests, datas, tools, executing

app = server.app


@app.route("/contests", methods=["GET"])
def contests_list():
    public_contests = datas.Contest.query
    got_data, page_cnt, page_idx, show_pages = tools.pagination(public_contests)
    return render_template("contests.html", contests=got_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=show_pages)


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
    status, target, can_see = contests.check_status(dat)
    info = dat.data
    can_edit = contests.check_super_access(dat)
    can_see = can_see or can_edit
    announcements = reversed(dat.announcements.filter_by(public=True).all())
    if can_edit:
        questions = reversed(dat.announcements.filter_by(question=True).all())
    else:
        questions = reversed(dat.announcements.filter_by(question=True, user=current_user.data).all())
    return render_template("contest.html", cid=idx, data=info, can_edit=can_edit, can_see=can_see, target=target,
                           status=status, announcements=announcements, questions=questions)


@app.route("/contest/<cid>/problem/<pid>", methods=["GET"])
def contest_problem(cid, pid):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    contests.check_access(cdat)
    info = cdat.data
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
    status = dat.submissions
    if "user" in request.form and len(request.form["user"]):
        user: datas.User = datas.User.query.filter_by(username=request.form["user"]).first_or_404()
        status = status.filter_by(user=user)
    if "pid" in request.form and len(request.form["pid"]):
        if request.form["pid"] not in dat.data["problems"]:
            abort(404)
        status = status.filter_by(pid=dat.data["problems"][request.form["pid"]])
    got_data, page_cnt, page_idx, show_pages = tools.pagination(status, True, page_str)
    out = []
    for obj in got_data:
        pid = obj.pid
        problem = "?"
        problem_name = "?"
        for k, v in dat.data["problems"].items():
            if v["pid"] == pid:
                problem = k
                problem_name = v["name"]
        result = obj.simple_result or "blank"
        can_see = current_user.has("admin") or current_user.id == obj.user.username
        out.append({"idx": str(obj.id),
                    "time": obj.time.timestamp(),
                    "user_id": obj.user.username,
                    "user_name": obj.user.display_name,
                    "problem": problem,
                    "problem_name": problem_name,
                    "lang": obj.language,
                    "result": result,
                    "can_see": can_see})
    ret = {"show_pages": show_pages, "page_cnt": page_cnt, "page": page_idx, "data": out}
    return jsonify(ret)


@app.route("/contest_action", methods=['POST'])
@login_required
def contest_action():
    idx = request.form["cid"]
    cdat = datas.Contest.query.filter_by(cid=idx).first_or_404()
    if not contests.check_super_access(cdat):
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
            start_time = datetime.fromisoformat(request.form["start_time"]).replace(second=0, microsecond=0)
            per = datas.Period.query.filter_by(start_time=start_time, contest=dat, is_virtual=True)
            if per.count():
                idx = per.first().id
            else:
                nw_per = datas.Period(start_time=start_time,
                                      end_time=start_time + timedelta(minutes=dat.data["elapsed"]),
                                      contest=dat,
                                      is_virtual=True)
                datas.add(nw_per)
                idx = nw_per.id
            dat.data["virtual_participants"][current_user.id] = idx
            flag_modified(dat, "data")
            datas.add(dat)
        except ValueError:
            abort(400)
        return "OK", 200


@app.route("/contest/<cid>/standing", methods=['POST'])
def contest_standing(cid):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    dt = time.time() - cdat.data["start"]
    dt = dt / 60 - cdat.data["elapsed"]
    can_see = (cdat.data["standing"]["public"] and
               (dt <= -cdat.data["standing"]["start_freeze"] or dt >= cdat.data["standing"]["end_freeze"]))
    if not can_see and not contests.check_super_access(cdat):
        abort(403)
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
                    "pids": list(cdat.data["problems"].keys()),
                    "penalty": cdat.data["penalty"],
                    "judging": per.judging})


@app.route("/contest/<cid>/question", methods=['POST'])
def contest_question(cid):
    cdat: datas.Contest = datas.Contest.query.filter_by(cid=cid).first_or_404()
    obj = datas.Announcement(time=datetime.now(),
                             title=request.form["title"],
                             content=request.form["content"],
                             user=current_user.data,
                             contest=cdat,
                             public=False,
                             question=True)
    datas.add(obj)
    return "", 200
