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
from flask_restx import Resource, fields, abort
from pygments import lexers
from werkzeug.utils import secure_filename

from .base import get_api_user, api_response, api, marshal_with, request_parser, Args, Form, paging, pagination
from ... import submitting, datas, objs, tools, executing, tasks, contests, constants, server

ns = api.namespace("general", path="/", description="General API endpoints")

prepares = {k: lexers.get_lexer_by_name(k) for lexer in lexers.get_all_lexers() for k in lexer[1]}

# region Models
submission_post_input = request_parser(
    Form("lang", "Programming language used for submission"),
    Form("code", "Source code to be submitted"),
    Form("pid", "Problem ID for the submission"),
    Form("cid", "Contest ID if applicable", required=False),
    Form("input", "Input for test submissions", required=False)
)
submission_post_output = ns.model("SubmissionOutput", {
    "submission_id": fields.String(description="ID of the submission created")
})
submission_get_input = request_parser(Args("submission_id", "Id of the submission to retrieve", int))
submission_get_output = ns.model("SubmissionDetailsOutput", {
    "lang": fields.String(description="Programming language used for the submission"),
    "source_code": fields.String(description="Source code of the submission"),
    "completed": fields.Boolean(description="Whether the submission is completed"),
    "ce_msg": fields.String(description="Compilation error message if any"),
    "result": fields.Raw(description="Result of the submission, varies based on problem type"),
    "input": fields.String(description="Input for test submissions", required=False),
    "output": fields.String(description="Output for test submissions", required=False)
})

status_item_model = ns.model("StatusItem", {
    "id": fields.String(description="Submission ID"),
    "time": fields.Float(description="Submission timestamp"),
    "user_id": fields.String(description="Username of submitter"),
    "user_name": fields.String(description="Display name of submitter"),
    "problem_id": fields.String(description="Problem ID"),
    "problem_name": fields.String(description="Problem name"),
    "lang": fields.String(description="Programming language"),
    "result": fields.String(description="Submission result"),
    "can_see": fields.Boolean(description="Whether current user can see full details"),
    "can_rejudge": fields.Boolean(description="Whether current user can rejudge"),
})
status_list_output = ns.model("StatusListOutput", {
    "show_pages": fields.List(fields.Integer),
    "page_count": fields.Integer,
    "page": fields.Integer,
    "data": fields.List(fields.Nested(status_item_model)),
})

rejudge_output = ns.model("RejudgeOutput", {
    "message": fields.String(default="OK")
})

judge_info_item = ns.model("JudgeInfoItem", {
    "name": fields.String(description="Language name/branch"),
    "compile": fields.String(description="Sample compile command"),
    "run": fields.String(description="Sample execution command"),
})
judge_info_output = ns.model("JudgeInfoOutput", {
    "langs": fields.List(fields.Nested(judge_info_item)),
})
# endregion

# region Parsers
status_get_input = request_parser(
    Args("user", type=str, required=False, help="Filter by username"),
    Args("pid", type=str, required=False, help="Filter by problem ID"),
    Args("result", type=str, required=False, help="Filter by result (e.g., AC, WA, TLE)"),
    Args("lang", type=str, required=False, help="Filter by programming language"),
    *paging()
)
rejudge_input = request_parser(
    Form("idx", "Submission ID to rejudge", type=int, required=True),
    Form("cid", "Contest ID if applicable", type=str, required=False)
)
rejudge_all_input = request_parser(
    Form("pid", "Problem ID to rejudge submissions for", type=str, required=True),
    Form("cid", "Contest ID if applicable", type=str, required=False),
    Form("result", "Filter by result (e.g., AC, WA, TLE)", type=str, required=False),
    Form("lang", "Filter by programming language", type=str, required=False),
)


# endregion

@ns.route("/submission")
class Submission(Resource):
    @ns.doc("submit_code")
    @ns.expect(submission_post_input)
    @marshal_with(ns, submission_post_output)
    def post(self):
        """Submit code for a problem or test."""
        args = submission_post_input.parse_args()
        user = get_api_user(args)
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
        """Get details of a specific submission."""
        args = submission_get_input.parse_args()
        user = get_api_user(args)
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
                for res in result_data.results:
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


@ns.route("/status")
class Status(Resource):
    @ns.doc("get_global_status")
    @ns.expect(status_get_input)
    @marshal_with(ns, status_list_output)
    def get(self):
        """Get global submission status (non-contest submissions)."""
        args = status_get_input.parse_args()
        user = get_api_user(args)

        status_query = datas.filter_by(datas.Submission, contest_id=None)
        if args["user"]:
            user_filter = datas.filter_by(datas.User, username=args["user"])
            if user_filter.count() == 0:
                status_query = status_query.filter_by(id=-1)
            else:
                status_query = status_query.filter_by(user=user_filter.first())
        if args["pid"]:
            status_query = status_query.filter_by(pid=args["pid"])
        if args["result"] and args["result"] in objs.TaskResult.__members__:
            status_query = status_query.filter_by(simple_result_flag=objs.TaskResult[args["result"]].name)
        if args["lang"] and args["lang"] in executing.langs:
            status_query = status_query.filter_by(language=args["lang"])

        got_data, page_cnt, page_idx, show_pages = pagination(status_query, args)
        out = []
        for obj in got_data:
            obj: datas.Submission
            problem = datas.filter_by(datas.Problem, pid=obj.pid)
            problem_name = problem.first().name if problem.count() else "unknown"
            result = obj.simple_result or "unknown"
            can_see = user.is_authenticated and (user.has(objs.Permission.admin) or
                                                 user.id == obj.user.username or
                                                 (obj.problem and obj.problem.user and
                                                  obj.problem.user.username == user.id))
            can_rejudge = can_see and (user.has(objs.Permission.admin) or (
                        obj.problem and obj.problem.user and obj.problem.user.username == user.id))
            out.append({
                "id": str(obj.id),
                "time": obj.time.timestamp(),
                "user_id": obj.user.username,
                "user_name": obj.user.display_name,
                "problem_id": obj.pid,
                "problem_name": problem_name,
                "lang": obj.language,
                "result": result,
                "can_see": can_see,
                "can_rejudge": can_rejudge
            })
        return api_response({
            "show_pages": show_pages, "page_count": page_cnt, "page": page_idx, "data": out
        })


@ns.route("/rejudge")
class Rejudge(Resource):
    @ns.doc("rejudge_submission")
    @ns.expect(rejudge_input)
    @marshal_with(ns, rejudge_output)
    def post(self):
        """Rejudge a single submission."""
        args = rejudge_input.parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            abort(403, "Authentication required to rejudge.")

        dat = datas.get_or_404(datas.Submission, args["idx"])
        if args["cid"]:
            if dat.contest.cid != args["cid"]:
                abort(400, "Submission does not belong to the specified contest.")
            cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=args["cid"])
            if not contests.check_super_access(cdat, user):  # Assuming this is the correct permission check
                abort(403, "Permission denied to rejudge in this contest.")
        else:
            if dat.contest_id is not None:
                abort(400, "Submission is part of a contest, specify CID.")
            if not user.has(objs.Permission.admin) and (not dat.problem or user.id != dat.problem.user.username):
                abort(403, "Permission denied to rejudge this submission.")
        if not dat.completed:
            abort(400, "Cannot rejudge an uncompleted submission.")
        tasks.rejudge(dat, "wait for rejudge")
        datas.add(dat)
        return api_response({"message": "Submission rejudged successfully."})


@ns.route("/rejudge_all")
class RejudgeAll(Resource):
    @ns.doc("rejudge_all_submissions")
    @ns.expect(rejudge_all_input)
    @marshal_with(ns, rejudge_output)
    def post(self):
        """Rejudge multiple submissions based on filters."""
        args = rejudge_all_input.parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            abort(403, "Authentication required to rejudge.")

        pid = args["pid"]
        if pid == "":
            abort(400, "Problem ID cannot be empty.")

        if args["cid"]:
            cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=args["cid"])
            if not contests.check_super_access(cdat, user):  # Assuming this is the correct permission check
                abort(403, "Permission denied to rejudge in this contest.")

            probs = cdat.datas.problems
            if pid not in probs:
                abort(404, "Problem not found in contest.")
            the_pid = probs[pid].pid
            prob = datas.first_or_404(datas.Problem, pid=the_pid)
            status_query = datas.filter_by(datas.Submission, problem_id=prob.id, contest_id=cdat.id, completed=True)
        else:
            if pid == "test":
                abort(400, "Test problem submissions cannot be rejudged en masse.")
            prob = datas.first_or_404(datas.Problem, pid=pid)
            if not user.has(objs.Permission.admin) and (not prob.user or user.id != prob.user.username):
                abort(403, "Permission denied to rejudge submissions for this problem.")
            status_query = datas.filter_by(datas.Submission, problem_id=prob.id, contest_id=None, completed=True)

        if args["result"] and args["result"] in objs.TaskResult.__members__:
            status_query = status_query.filter_by(simple_result_flag=objs.TaskResult[args["result"]].name)
        if args["lang"] and args["lang"] in executing.langs:
            status_query = status_query.filter_by(language=args["lang"])

        for a_submit in status_query:
            tasks.rejudge(a_submit, "wait for rejudge")
            datas.add(a_submit)

        return api_response({"message": "All matching submissions rejudged successfully."})


@ns.route("/judge_info")
class JudgeInfo(Resource):
    @ns.doc("get_judge_information")
    @marshal_with(ns, judge_info_output)
    def get(self):
        """Get information about supported programming languages and judge commands."""
        out = []
        for lang in executing.langs.values():
            out.append({"name": lang.branch, "compile": " ".join(lang.sample_compile_cmd),
                        "run": " ".join(lang.sample_exec_cmd)})
        return api_response({"langs": out})


problem_file_input = request_parser(
    Args("cid", "Contest ID if applicable", type=str, required=False)
)


@ns.route("/problem_file/<string:idx>/<string:filename>")
class ProblemFile(Resource):
    @ns.doc("get_problem_file")
    @ns.expect(problem_file_input)
    def get(self, idx: str, filename: str):
        """Serve a public file associated with a problem."""
        args = problem_file_input.parse_args()
        user = get_api_user(args)
        idx = secure_filename(idx)
        filename = secure_filename(filename)

        if args["cid"]:
            cdat = datas.first_or_404(datas.Contest, cid=args["cid"])
            found_problem = False
            for obj in cdat.datas.problems.values():
                if obj.pid == idx:
                    found_problem = True
                    break
            if not found_problem:
                abort(404, "Problem not found in contest.")
            contests.check_access(cdat, user)
        else:
            pdat = datas.first_or_404(datas.Problem, pid=idx)
            dat = pdat.datas
            if not pdat.is_public:
                if not user.is_authenticated:
                    abort(403)
                if not user.has(objs.Permission.admin) and user.id not in dat.users:
                    abort(403)
        target = constants.problem_path / idx / "public_file" / filename
        if not target.is_file():
            abort(404, "File not found.")
        return server.sending_file(target)
