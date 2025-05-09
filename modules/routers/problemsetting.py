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

import os
from pathlib import Path
from typing import Iterable

from flask import abort, render_template, request
from flask_login import login_required
from werkzeug.utils import secure_filename

from .. import tools, server, login, executing, problemsetting, datas, config, objs
from ..constants import preparing_problem_path, problem_path
from ..objs import Permission

app = server.app


@app.route("/problemsetting", methods=['GET'])
@login_required
def my_problems():
    user = login.check_user(Permission.make_problems)
    problem_obj = user.data.problems.filter(datas.Problem.pid != "test")
    got_data, page_cnt, page_idx, show_pages = tools.pagination(problem_obj)
    problems_dat = []
    for obj in got_data:
        problems_dat.append({"pid": obj.pid, "name": obj.name})
    return render_template("my_problems.html", problems=problems_dat, title="我的題目", page_cnt=page_cnt,
                           page_idx=page_idx, show_pages=show_pages)


@app.route("/problemsetting_all", methods=['GET'])
@login_required
def all_problems():
    login.check_user(Permission.admin)
    problem_obj = datas.do_filter(datas.Problem, datas.Problem.pid != "test")
    got_data, page_cnt, page_idx, show_pages = tools.pagination(problem_obj)
    problems_dat = []
    for obj in got_data:
        problems_dat.append({"pid": obj.pid, "name": obj.name})
    return render_template("my_problems.html", problems=problems_dat, title="所有題目", page_cnt=page_cnt,
                           page_idx=page_idx, show_pages=show_pages)


@app.route("/problemsetting_new", methods=['GET', 'POST'])
@login_required
def create_problem():
    user = login.check_user(Permission.make_problems)
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
    pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=idx)
    dat = pdat.new_datas
    user = login.check_user(Permission.make_problems, dat.users)
    o = problemsetting.check_background_action(idx)
    if o is not None:
        return render_template("pleasewaitlog.html", action=o[1], log=o[0])
    p_path = preparing_problem_path / idx
    public_files: list[str] = [f.name for f in (p_path / "public_file").iterdir() if f.name != ".gitkeep"]
    default_checkers = [s for s in os.listdir("testlib/checkers") if s.endswith(".cpp")]
    default_interactors = [s for s in os.listdir("testlib/interactors") if s.endswith(".cpp")]
    if "default" not in dat.groups:
        dat.groups["default"] = objs.TestcaseGroup()
    action_path = p_path / "actions"
    action_files: Iterable[Path] = action_path.iterdir() if action_path.is_dir() else []
    actions = []
    for f in action_files:
        if f.suffix == ".json":
            actions.append(f.stem)
    return render_template("problemsetting.html", dat=dat, pid=idx,
                           versions=problemsetting.query_versions(pdat), enumerate=enumerate,
                           public_files=public_files, default_checkers=default_checkers,
                           langs=executing.langs.keys(), default_interactors=default_interactors,
                           username=user.id, pdat=pdat, actions=actions)


@app.route("/problemsetting_action", methods=['POST'])
@login_required
def problem_action():
    idx = request.form["pid"]
    idx = secure_filename(idx)
    pdat = datas.first_or_404(datas.Problem, pid=idx)
    if (problem_path / idx / "waiting").is_file():
        abort(503)
    if problemsetting.check_background_action(idx) is not None:
        abort(503)
    dat = pdat.data
    login.check_user(Permission.make_problems, dat["users"])
    return problemsetting.action(request.form)


@app.route("/problemsetting_preview", methods=["GET"])
@server.limiter.limit(config.server.file_limit)
@login_required
def problem_preview():
    idx = request.args["pid"]
    pdat = datas.first_or_404(datas.Problem, pid=idx)
    if (problem_path / idx / "waiting").is_file():
        return render_template("pleasewait.html", action=tools.read(pdat.path / "waiting"))
    dat = pdat.new_datas
    login.check_user(Permission.make_problems, dat.users)
    return problemsetting.preview(request.args, pdat)
