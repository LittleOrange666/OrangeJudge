"""
OrangeJudge, a competitive programming platform

Copyright (C) 2024-2026 LittleOrange666 (orangeminecraft123@gmail.com)

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
import io
import re
import zipfile

from flask_login import current_user
from werkzeug.datastructures import FileStorage

from . import datas, executing, tasks, contests, config, objs, tools, constants, login, server


def test_submit(lang: str, code: str, inp: str, user: login.User | None = None) -> str:
    if not inp.endswith("\n"):
        inp += "\n"
    if datas.count(datas.Submission, user=user.data, completed=False) >= config.judge.pending_limit:
        server.custom_abort(409, "Too many uncompleted submissions")
    if len(code) > config.judge.file_size * 1024:
        server.custom_abort(400, "Source code file too large")
    if lang not in executing.langs:
        server.custom_abort(404, "Language not supported")
    ext = executing.langs[lang].source_ext
    fn = constants.source_file_name + ext
    user_id = user.data.id
    problem_id = datas.first(datas.Problem, pid="test").id
    with datas.SessionContext():
        dat = datas.Submission(source=fn, time=datetime.datetime.now(), user_id=user_id,
                               problem_id=problem_id, language=lang,
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
        server.custom_abort(400, "Source code file too large")
    pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
    if lang not in executing.langs:
        server.custom_abort(404, "Language not supported")
    if pdat.datas.output_only:
        server.custom_abort(400, "This is an output-only problem, please submit output files")
    if not pdat.lang_allowed(lang):
        server.custom_abort(400, "Language not allowed for this problem")
    ext = executing.langs[lang].source_ext
    fn = constants.source_file_name + ext
    user_id = user.data.id
    problem_id = pdat.id
    with datas.SessionContext():
        dat = datas.Submission(source=fn, time=datetime.datetime.now(), user_id=user_id,
                               problem_id=problem_id, language=lang, data={}, pid=pid, simple_result="waiting",
                               queue_position=0, simple_result_flag=objs.TaskResult.PENDING.name)
        if cid is not None:
            cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
            contests.check_access(cdat, user)
            per_id = contests.check_period(cdat, user)
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


output_file_pattern = re.compile(r"^output_(\d+)\.txt$")


def collect_outputs(files: list[FileStorage], testcase_count: int) -> dict[int, bytes]:
    """
    Collect output files of an output-only submission.

    Every uploaded file is either an ``output_<k>.txt`` file or a zip archive containing such files
    (directories inside the archive are ignored). ``k`` is the 1-based testcase codename.
    """
    limit = constants.output_only_max_size
    total = 0
    outputs: dict[int, bytes] = {}

    def add(name: str, content: bytes):
        nonlocal total
        m = output_file_pattern.match(name.replace("\\", "/").split("/")[-1])
        if m is None:
            return
        k = int(m.group(1))
        if not 1 <= k <= testcase_count:
            server.custom_abort(400, f"Invalid output file {name!r}: there are only {testcase_count} testcases")
        total += len(content)
        if total > limit:
            server.custom_abort(400, "Output files too large")
        outputs[k] = content

    for file in files:
        if file is None or not file.filename:
            continue
        content = file.stream.read(limit + 1)
        if len(content) > limit:
            server.custom_abort(400, "Output files too large")
        if file.filename.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for member in zf.infolist():
                        if member.is_dir():
                            continue
                        if member.file_size > limit:
                            server.custom_abort(400, "Output files too large")
                        add(member.filename, zf.read(member))
            except zipfile.BadZipFile:
                server.custom_abort(400, "Invalid zip file")
        else:
            add(file.filename, content)
    return outputs


def submit_output_only(pid: str, files: list[FileStorage], cid: str | None = None,
                       user: login.User | None = None) -> str:
    """
    Submit outputs for an output-only (CMS "OutputOnly") problem.

    Testcases whose output is not included are taken from the previous output-only submission of the same user
    to the same problem (in the same contest), like CMS does.
    """
    if user is None:
        user = current_user
    if datas.count(datas.Submission, user=user.data, completed=False) >= config.judge.pending_limit:
        server.custom_abort(409, "Too many uncompleted submissions")
    pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
    problem_info = pdat.datas
    if not problem_info.output_only:
        server.custom_abort(400, "This problem is not an output-only problem")
    testcase_count = len(problem_info.ordered_testcases())
    outputs = collect_outputs(files, testcase_count)
    if not outputs:
        server.custom_abort(400, "No output file found, files should be named as output_<k>.txt")
    fn = constants.output_only_source
    contest_id = None
    if cid is not None:
        contest_id = datas.first_or_404(datas.Contest, cid=cid).id
    previous: datas.Submission | None = (datas.filter_by(datas.Submission, user_id=user.data.id, problem_id=pdat.id,
                                                         language=constants.output_only_language,
                                                         contest_id=contest_id)
                                         .order_by(datas.Submission.id.desc()).first())
    with datas.SessionContext():
        dat = datas.Submission(source=fn, time=datetime.datetime.now(), user_id=user.data.id,
                               problem_id=pdat.id, language=constants.output_only_language, data={}, pid=pid,
                               simple_result="waiting", queue_position=0,
                               simple_result_flag=objs.TaskResult.PENDING.name)
        if cid is not None:
            cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
            contests.check_access(cdat, user)
            per_id = contests.check_period(cdat, user)
            dat.contest = cdat
            if per_id:
                dat.period_id = per_id
                if cdat.datas.pretest != objs.PretestType.no:
                    dat.just_pretest = True
        datas.add(dat)
        datas.flush()
        idx = str(dat.id)
        outputs_path = dat.path / "outputs"
        outputs_path.mkdir(parents=True, exist_ok=True)
        summary = []
        for k in range(1, testcase_count + 1):
            name = constants.output_only_output_name.format(k)
            if k in outputs:
                (outputs_path / name).write_bytes(outputs[k])
                summary.append(f"{name}: submitted ({len(outputs[k])} bytes)")
            elif previous is not None and (previous.path / "outputs" / name).is_file():
                tools.copy(previous.path / "outputs" / name, outputs_path / name)
                summary.append(f"{name}: from submission #{previous.id}")
            else:
                summary.append(f"{name}: missing")
        tools.write("\n".join(summary) + "\n", dat.path / fn)
        dat.queue_position = tasks.enqueue(dat.id)
        datas.add(dat)
    return idx
