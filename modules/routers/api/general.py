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

from flask import request, abort

from .base import blueprint, get_api_user, api_response
from ... import submitting, datas, objs, tools


@blueprint.route("/submit", methods=["POST"])
def submit():
    user = get_api_user(request.form["username"])
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    pid = request.form["pid"]
    cid = request.form.get("cid")
    if pid == "test":
        inp = request.form["input"]
        idx = submitting.test_submit(lang, code, inp, user)
    else:
        idx = submitting.submit(lang, pid, code, cid, user)
    return api_response({"submission_id": idx})


@blueprint.route("/submission", methods=["GET"])
def submission():
    user = get_api_user(request.args["username"])
    idx = tools.to_int(request.args["submission_id"])
    dat = datas.first_or_404(datas.Submission, id=idx)
    if not user.has(objs.Permission.admin) and dat.user_id != user.data.id:
        abort(403)
    lang = dat.language
    source = tools.read(dat.path / dat.source)
    completed = dat.completed
    ce_msg = dat.ce_msg
    pdat: datas.Problem = dat.problem
    ret = {"lang": lang,
           "source_code": source,
           "completed": completed,
           "ce_msg": ce_msg}
    info = dat.datas
    if pdat.pid == "test":
        ret["result"] = dat.simple_result or "unknown"
        ret["input"] = tools.read_default(dat.path / info.infile)
        ret["output"] = tools.read_default(dat.path / info.outfile)
    else:
        result_data = dat.results
        results = result_data.results
        group_results = {}
        result = {}
        if completed and not info.JE:
            result["CE"] = result_data.CE
            gpr = result_data.group_results
            if len(gpr) > 0 and type(next(iter(gpr.values()))) is objs.GroupResult:
                group_results = {k: {"result": v.result.name,
                                     "gained_score": v.gained_score,
                                     "time": v.time,
                                     "mem": v.mem} for k, v in gpr}
            detail = []
            for res in results:
                detail.append({
                    "result": res.result.name,
                    "time": res.time,
                    "mem": res.mem,
                    "score": res.score
                })
            result["total_score"] = result_data.total_score
            result["group_result"] = group_results
            result["detail"] = detail
        ret["result"] = result
    return api_response(ret)
