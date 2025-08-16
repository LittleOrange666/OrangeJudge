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
from flask_restx import Resource, fields, reqparse, abort
from .base import get_api_user, api_response, api, marshal_with
from ... import submitting, datas, objs, tools

ns = api.namespace("general", path="/", description="General API endpoints")

submission_post_input = reqparse.RequestParser()
submission_post_input.add_argument("username", type=str, required=True, help="Username of the user submitting the code")
submission_post_input.add_argument("lang", type=str, required=True, help="Programming language used for submission")
submission_post_input.add_argument("code", type=str, required=True, help="Source code to be submitted")
submission_post_input.add_argument("pid", type=str, required=True, help="Problem ID for the submission")
submission_post_input.add_argument("cid", type=str, required=False, help="Contest ID if applicable")
submission_post_input.add_argument("input", type=str, required=False, help="Input for test submissions")
submission_post_output = ns.model("SubmissionOutput", {
    "submission_id": fields.String(description="ID of the submission created")
})
submission_get_input = reqparse.RequestParser()
submission_get_input.add_argument("username", type=str, required=True, help="Username of the user submitted the code")
submission_get_input.add_argument("submission_id", type=int, required=True, help="Id of the submission to retrieve")
submission_get_output = ns.model("SubmissionDetailsOutput", {
    "lang": fields.String(description="Programming language used for the submission"),
    "source_code": fields.String(description="Source code of the submission"),
    "completed": fields.Boolean(description="Whether the submission is completed"),
    "ce_msg": fields.String(description="Compilation error message if any"),
    "result": fields.Raw(description="Result of the submission, varies based on problem type"),
    "input": fields.String(description="Input for test submissions", required=False),
    "output": fields.String(description="Output for test submissions", required=False)
})


@ns.route("/submission")
class Submission(Resource):
    @ns.doc("submit_code")
    @ns.expect(submission_post_input)
    @marshal_with(ns, submission_post_output)
    def post(self):
        args = submission_post_input.parse_args()
        user = get_api_user(args["username"])
        lang = args["lang"]
        code = args["code"].replace("\n\n", "\n")
        pid = args["pid"]
        cid = args.get("cid")
        if pid == "test":
            inp = args["input"]
            idx = submitting.test_submit(lang, code, inp, user)
        else:
            idx = submitting.submit(lang, pid, code, cid, user)
        return api_response({"submission_id": idx})

    @ns.doc("submission_details")
    @ns.expect(submission_get_input)
    @marshal_with(ns, submission_get_output)
    def get(self):
        args = submission_get_input.parse_args()
        user = get_api_user(args["username"])
        idx = args["submission_id"]
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
