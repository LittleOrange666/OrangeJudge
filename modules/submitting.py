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

from flask import abort
from flask_login import current_user

from . import datas, executing, tasks, contests, config, objs, tools, constants, login, server


def test_submit(lang: str, code: str, inp: str, user: login.User | None = None) -> str:
    if not inp.endswith("\n"):
        inp += "\n"
    if lang not in executing.langs:
        abort(404)
    ext = executing.langs[lang].source_ext
    fn = constants.source_file_name + ext
    dat = datas.Submission(source=fn, time=datetime.datetime.now(), user=user.data,
                           problem=datas.first(datas.Problem, pid="test"), language=lang,
                           data={"infile": "in.txt", "outfile": "out.txt"}, pid="test", simple_result="waiting",
                           queue_position=0, simple_result_flag=objs.TaskResult.PENDING.name)
    datas.add(dat)
    datas.flush()
    idx = str(dat.id)
    tools.write(code, dat.path / fn)
    tools.write(inp, dat.path / "in.txt")
    dat.queue_position = tasks.enqueue(dat.id)
    datas.add(dat)
    return idx


def submit(lang: str, pid: str, code: str, cid: str | None = None, user: login.User | None = None) -> str:
    if user is None:
        user = current_user
    if datas.count(datas.Submission, user=user.data, completed=False) >= config.judge.pending_limit:
        server.custom_abort(409, "Too many uncompleted submissions")
    if len(code) > config.judge.file_size * 1024:
        abort(400)
    pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
    if lang not in executing.langs:
        abort(404)
    if not pdat.lang_allowed(lang):
        abort(400)
    ext = executing.langs[lang].source_ext
    fn = constants.source_file_name + ext
    dat = datas.Submission(source=fn, time=datetime.datetime.now(), user=user.data,
                           problem=pdat, language=lang, data={}, pid=pid, simple_result="waiting",
                           queue_position=0, simple_result_flag=objs.TaskResult.PENDING.name)
    if cid is not None:
        cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        contests.check_access(cdat)
        per_id = contests.check_period(cdat)
        dat.contest = cdat
        if per_id:
            dat.period_id = per_id
            if cdat.datas.pretest != objs.PretestType.no:
                dat.just_pretest = True
    datas.add(dat)
    datas.flush()
    idx = str(dat.id)
    tools.write(code, dat.path / fn)
    dat.queue_position = tasks.enqueue(dat.id)
    datas.add(dat)
    return idx
