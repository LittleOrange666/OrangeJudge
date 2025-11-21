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

import time
from datetime import datetime, timedelta

from flask import abort, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm.attributes import flag_modified

from .general import render_problem
from .. import server, login, contests, datas, tools, executing, objs, constants
from ..objs import Permission

app = server.app


@app.route("/contests", methods=["GET"])
def contests_list():
    public_contests = datas.Contest.query
    if not login.has_permission(Permission.admin):
        public_contests = public_contests.filter_by(hidden=False)
    got_data, page_cnt, page_idx, show_pages = tools.pagination(public_contests)
    contests_data = [(contest.cid, contest.name, contest.datas, contest.can_virtual()) for contest in got_data]
    return render_template("contests.html", contests=contests_data, page_cnt=page_cnt, page_idx=page_idx,
                           show_pages=show_pages, cur_time=time.time())


@app.route("/create_contest", methods=["POST"])
@login_required
def create_contest():
    login.check_user(Permission.make_problems)
    name = request.form.get("contest_name")
    if not name or len(name) > 120:
        abort(400)
    idx = contests.create_contest(name, current_user.data)
    return "/contest/" + idx, 200


@app.route("/contest/<idx>", methods=["GET"])
def contest_page(idx):
    dat: datas.Contest = datas.first(datas.Contest, cid=idx)
    if dat is None:
        server.custom_abort(404, "未找到比賽")
    can_edit = contests.check_super_access(dat)
    if not can_edit and dat.hidden:
        server.custom_abort(404, "未找到比賽")
    status, target, can_see = contests.check_status(dat)
    info = dat.datas
    can_see = can_see or can_edit
    announcements = reversed(dat.announcements.filter_by(public=True).all())
    if can_edit:
        questions = reversed(dat.announcements.filter_by(question=True).all())
    else:
        user_data = current_user.data if current_user.is_authenticated else None
        questions = reversed(dat.announcements.filter_by(question=True, user=user_data).all())
    displayed = not dat.hidden
    return render_template("contest.html", cid=idx, data=info, can_edit=can_edit, can_see=can_see, target=target,
                           status=status.name, announcements=announcements, questions=questions, cur_time=time.time(),
                           languages=sorted(executing.langs.keys()), can_filter_results=constants.can_filter_results,
                           displayed=displayed)


@app.route("/contest/<cid>/problem/<pid>", methods=["GET"])
def contest_problem(cid, pid):
    cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    contests.check_access(cdat)
    info = cdat.datas
    if pid not in info.problems:
        abort(404)
    idx = info.problems[pid].pid
    pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=idx)
    dat = pdat.datas
    langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
    return render_problem(dat, idx, langs, is_contest=True, cid=cid, cname=cdat.name, pidx=pid)


@app.route("/contest/<cid>/status/<page_str>", methods=["POST"])
def contest_status(cid, page_str):
    dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    info = dat.datas
    status = dat.submissions
    if "user" in request.form and len(request.form["user"]):
        user: datas.User = datas.first_or_404(datas.User, username=request.form["user"])
        status = status.filter_by(user=user)
    if "pid" in request.form and len(request.form["pid"]):
        if request.form["pid"] not in info.problems:
            abort(404)
        status = status.filter_by(pid=info.problems[request.form["pid"]].pid)
    if "result" in request.form and request.form["result"] in objs.TaskResult.__members__:
        result = objs.TaskResult[request.form["result"]]
        status = status.filter_by(simple_result_flag=result.name)
    if "lang" in request.form and request.form["lang"] in executing.langs:
        status = status.filter_by(language=request.form["lang"])
    got_data, page_cnt, page_idx, show_pages = tools.pagination(status, True, page_str)
    out = []
    for obj in got_data:
        obj: datas.Submission
        pid = obj.pid
        problem = "?"
        problem_name = "???"
        for k, v in info.problems.items():
            if v.pid == pid:
                problem = k
                problem_name = v.name
        can_see = current_user.is_authenticated and (login.has_permission(Permission.admin) or
                                                     current_user.id == obj.user.username)
        can_rejudge = contests.check_super_access(dat)
        can_know = can_see or info.standing.public
        result = obj.simple_result or "unknown"
        if can_know:
            out.append({"idx": str(obj.id),
                        "time": obj.time.timestamp(),
                        "user_id": obj.user.username,
                        "user_name": obj.user.display_name,
                        "problem": problem,
                        "problem_name": problem_name,
                        "lang": obj.language,
                        "result": result,
                        "can_see": can_see,
                        "can_rejudge": can_rejudge})
        else:
            out.append({"idx": str(obj.id),
                        "time": obj.time.timestamp(),
                        "user_id": "???",
                        "user_name": "???",
                        "problem": "?",
                        "problem_name": "???",
                        "lang": "???",
                        "result": "???",
                        "can_see": can_see,
                        "can_rejudge": can_rejudge})
    ret = {"show_pages": show_pages, "page_cnt": page_cnt, "page": page_idx, "data": out}
    return jsonify(ret)


@app.route("/contest_action", methods=['POST'])
@login_required
def contest_action():
    idx = request.form["cid"]
    cdat = datas.first_or_404(datas.Contest, cid=idx)
    if not contests.check_super_access(cdat):
        abort(403)
    return contests.action(request.form, cdat)


@app.route("/contest/<cid>/register", methods=['POST'])
@login_required
def contest_register(cid):
    dat = datas.first_or_404(datas.Contest, cid=cid)
    per = datas.get_or_404(datas.Period, dat.main_period_id)
    info = dat.datas
    if not info.can_register or per.is_over():
        abort(403)
    if current_user.id in info.participants:
        abort(409)
    info.participants.append(current_user.id)
    dat.datas = info
    flag_modified(dat, "data")
    datas.add(dat)
    return "OK", 200


@app.route("/contest/<cid>/unregister", methods=['POST'])
@login_required
def contest_unregister(cid):
    dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    info = dat.datas
    if not info.can_register:
        abort(403)
    if current_user.id not in info.participants:
        abort(409)
    info.participants.remove(current_user.id)
    dat.datas = info
    flag_modified(dat, "data")
    datas.add(dat)
    return "OK", 200


@app.route("/contest/<cid>/virtual", methods=['GET', 'POST'])
@login_required
def virtual_register(cid):
    dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    info = dat.datas
    if not dat.can_virtual():
        abort(403)
    if current_user.id in info.virtual_participants:
        abort(409)
    if request.method == "GET":
        return render_template("virtual_register.html", cid=cid, name=dat.name)
    else:
        start_time: datetime = tools.to_datetime(request.form["start_time"], second=0, microsecond=0)
        per = datas.filter_by(datas.Period, start_time=start_time, contest=dat, is_virtual=True)
        if per.count() > 0:
            idx = per.first().id
        else:
            nw_per = datas.Period(start_time=start_time,
                                  end_time=start_time + timedelta(minutes=info.elapsed),
                                  contest=dat,
                                  is_virtual=True)
            datas.add(nw_per)
            datas.flush()
            idx = nw_per.id
        info.virtual_participants[current_user.id] = idx
        flag_modified(dat, "data")
        datas.add(dat)
        return "OK", 200


@app.route("/contest/<cid>/standing", methods=['POST'])
def contest_standing(cid):
    cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    info = cdat.datas
    dt = time.time() - info.start
    dt = dt / 60 - info.elapsed
    can_see = (info.standing.public and
               (dt <= -info.standing.start_freeze or dt >= info.standing.end_freeze))
    if not can_see and not contests.check_super_access(cdat):
        abort(403)
    dat = contests.get_standing(cid)
    return jsonify(dat)


@app.route("/contest/<cid>/question", methods=['POST'])
def contest_question(cid):
    cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    if len(request.form["title"]) > 80:
        abort(400)
    if len(request.form["content"]) > 1000:
        abort(400)
    obj = datas.Announcement(time=datetime.now(),
                             title=request.form["title"],
                             content=request.form["content"],
                             user=current_user.data,
                             contest=cdat,
                             public=False,
                             question=True)
    datas.add(obj)
    return "", 200


@app.route('/reject', methods=['POST'])
@login_required
def reject():
    idx = request.form["idx"]
    cid = request.form["cid"]
    dat = datas.get_or_404(datas.Submission, tools.to_int(idx))
    if dat.contest.cid != cid:
        abort(400)
    cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
    if not contests.check_super_access(cdat):
        abort(403)
    if not dat.completed:
        abort(400)
    contests.reject(dat)
    datas.add(dat)
    return "OK", 200
