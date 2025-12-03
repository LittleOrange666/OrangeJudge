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

from flask_restx import Resource, fields
from sqlalchemy.orm.attributes import flag_modified

from .base import (
    api,
    api_response,
    get_api_user,
    marshal_with,
    request_parser,
    Args,
    Form,
    paging,
    pagination,
    base_request_parser
)
from ... import contests, datas, executing, objs, tools, constants, server
from ...objs import Permission

ns = api.namespace("contests", path="/contest", description="Contest related API endpoints")

# endregion

# region Models
contest_summary_model = ns.model("ContestSummary", {
    "cid": fields.String(description="Contest ID"),
    "name": fields.String(description="Contest Name"),
    "start_time": fields.Float(description="Start time timestamp"),
    "end_time": fields.Float(description="End time timestamp"),
    "status": fields.String(description="Contest status (Running, Upcoming, Ended)"),
    "can_virtual": fields.Boolean(description="Whether virtual participation is allowed"),
    "can_register": fields.Boolean(description="Whether registration is allowed"),
    "is_registered": fields.Boolean(description="Whether the user is registered for the contest"),
    "elapsed": fields.Integer(description="Contest duration in minutes"),
})
contest_list_output = ns.model("ContestListOutput", {
    "data": fields.List(fields.Nested(contest_summary_model), description="List of contests"),
    "page": fields.Integer(description="Current page number"),
    "page_count": fields.Integer(description="Total number of pages"),
    "show_pages": fields.List(fields.Integer, description="List of page numbers to display in pagination"),
})
create_contest_output = ns.model("CreateContestOutput", {
    "contest_id": fields.String(description="ID of the newly created contest")
})
ok_output = ns.model("OKOutput", {"message": fields.String(default="OK")})

problem_in_contest_model = ns.model("ProblemInContest", {
    "pid": fields.String(description="Problem ID within the contest"),
    "name": fields.String(description="Problem name"),
})
announcement_model = ns.model("Announcement", {
    "title": fields.String(description="Announcement title"),
    "content": fields.String(description="Announcement content"),
    "time": fields.Float(description="Announcement timestamp"),
})
question_model = ns.model("Question", {
    "id": fields.Integer(description="Question ID"),
    "title": fields.String(description="Question title"),
    "content": fields.String(description="Question content"),
    "time": fields.Float(description="Question timestamp"),
    "author": fields.String(description="Username of the author"),
    "answer": fields.String(description="Content of the reply to this question, if any"),
})
contest_details_output = ns.model("ContestDetailsOutput", {
    "cid": fields.String(description="Contest ID"),
    "name": fields.String(description="Contest name"),
    "description": fields.String(description="Contest description"),
    "start_time": fields.Float(description="Start time timestamp"),
    "end_time": fields.Float(description="End time timestamp"),
    "status": fields.String(description="Contest status"),
    "can_edit": fields.Boolean(description="Whether the user can edit the contest"),
    "can_see_problems": fields.Boolean(description="Whether the user can see problems"),
    "problems": fields.List(fields.Nested(problem_in_contest_model), description="List of problems in the contest"),
    "announcements": fields.List(fields.Nested(announcement_model), description="List of announcements"),
    "questions": fields.List(fields.Nested(question_model), description="List of questions"),
    "is_registered": fields.Boolean(description="Whether the user is registered"),
    "is_virtual_participant": fields.Boolean(description="Whether the user is a virtual participant"),
    "elapsed": fields.Integer(description="Contest duration in minutes"),
    "can_register": fields.Boolean(description="Whether registration is allowed"),
})
submission_status_model = ns.model("SubmissionStatus", {
    "id": fields.String(description="Submission ID"),
    "time": fields.Float(description="Submission timestamp"),
    "user_id": fields.String(description="User ID"),
    "user_name": fields.String(description="User display name"),
    "problem_id": fields.String(description="Problem ID"),
    "problem_name": fields.String(description="Problem name"),
    "lang": fields.String(description="Programming language"),
    "result": fields.String(description="Submission result"),
    "can_see": fields.Boolean(description="Whether details are visible"),
})
contest_status_output = ns.model("ContestStatusOutput", {
    "data": fields.List(fields.Nested(submission_status_model), description="List of submissions"),
    "page": fields.Integer(description="Current page number"),
    "page_count": fields.Integer(description="Total number of pages"),
    "show_pages": fields.List(fields.Integer, description="List of page numbers to display"),
})
standing_output = ns.model("StandingOutput", {
    "submissions": fields.List(fields.Nested(ns.model("StandingSubmission", {
        "user": fields.String(description="User ID"),
        "pid": fields.String(description="Problem ID"),
        "time": fields.Float(description="Submission timestamp"),
        "scores": fields.Raw(description="Scores per problem"),
        "total_score": fields.Float(description="Total score"),
        "pretest": fields.Boolean(description="Whether it's a pretest"),
        "per": fields.Integer(description="Period ID"),
    })), description="List of standing submissions"),
    "rule": fields.String(description="Contest rule type"),
    "pids": fields.List(fields.String, description="List of problem IDs"),
    "penalty": fields.Integer(description="Penalty time"),
    "pers": fields.List(fields.Nested(ns.model("StandingPeriod", {
        "start_time": fields.Float(description="Period start time"),
        "judging": fields.Boolean(description="Whether judging is in progress"),
        "id": fields.Integer(description="Period ID"),
    })), description="List of periods"),
    "main_per": fields.Integer(description="Main period ID"),
    "participants": fields.List(fields.String, description="List of participants"),
    "virtual_participants": fields.Raw(description="Virtual participants data"),
})
contest_problem_detail_model = ns.model("ContestProblemDetail", {
    "pid": fields.String(description="Problem ID within the contest"),
    "internal_pid": fields.String(description="System-wide Problem ID"),
    "name": fields.String(description="Problem name"),
    "description": fields.String(description="Problem description HTML"),
    "allowed_languages": fields.List(fields.String, description="List of allowed languages"),
    "contest_cid": fields.String(description="Contest ID"),
    "contest_name": fields.String(description="Contest name"),
    "time_limit": fields.Float(description="Time limit in seconds"),
    "memory_limit": fields.Integer(description="Memory limit in MB"),
    "statement": fields.String(description="Problem statement in Markdown format"),
    "statement_html": fields.String(description="Problem statement in HTML format"),
    "samples": fields.List(fields.Nested(ns.model("ContestSampleTestcase", {
        "input": fields.String(description="Sample input for the problem"),
        "output": fields.String(description="Sample output for the problem")
    })), description="List of sample testcases"),
})
# endregion

# region Parsers
contest_list_input = request_parser(*paging())
create_contest_input = request_parser(Form("contest_name", "Name of the new contest", required=True))
contest_status_input = request_parser(
    Form("user", type=str, required=False),
    Form("pid", type=str, required=False),
    Form("result", type=str, required=False),
    Form("lang", type=str, required=False),
    Args("page", type=int, default=1),
    Args("page_size", type=int, default=constants.page_size)
)
virtual_register_input = request_parser(
    Form("start_time", "Start time for virtual contest (YYYY-MM-DD HH:MM)", required=True))
question_input = request_parser(
    Form("title", "Title of the question", required=True),
    Form("content", "Content of the question", required=True)
)


# endregion

@ns.route("")
class ContestList(Resource):
    @ns.doc("list_contests")
    @ns.expect(contest_list_input)
    @marshal_with(ns, contest_list_output)
    def get(self):
        """List all available contests"""
        args = contest_list_input.parse_args()
        user = get_api_user(args, require_login=False)

        query = datas.Contest.query
        if not user.is_authenticated or not user.has(Permission.make_problems):
            query = query.filter_by(hidden=False)

        got_data, page_cnt, page_idx, show_pages = pagination(query, args)

        contests_data = []
        for contest in got_data:
            contest: datas.Contest
            info: objs.ContestData = contest.datas
            status, _, _ = contests.check_status(contest, user)
            can_vir = contest.can_virtual() and user.is_authenticated and user.id not in info.virtual_participants
            can_reg = info.can_register and user.is_authenticated
            is_reg = user.is_authenticated and user.id in info.participants
            contests_data.append({
                "cid": contest.cid,
                "name": contest.name,
                "start_time": info.start,
                "elapsed": info.elapsed,
                "end_time": info.start + info.elapsed * 60,
                "status": status.name,
                "can_virtual": can_vir,
                "can_register": can_reg,
                "is_registered": is_reg
            })

        return api_response({
            "data": contests_data,
            "page": page_idx,
            "page_count": page_cnt,
            "show_pages": show_pages,
        })

    @ns.doc("create_contest")
    @ns.expect(create_contest_input)
    @marshal_with(ns, create_contest_output)
    def post(self):
        """Create a new contest"""
        args = create_contest_input.parse_args()
        user = get_api_user(args, required=Permission.make_problems)
        name = args["contest_name"]
        if not name or len(name) > 120:
            server.custom_abort(400, "Invalid contest name length")
        cid = contests.create_contest(name, user.data)
        return api_response({"contest_id": cid})


@ns.route("/<string:cid>")
@ns.param("cid", "The contest ID")
class Contest(Resource):
    @ns.doc("get_contest_details")
    @ns.expect(base_request_parser)
    @marshal_with(ns, contest_details_output)
    def get(self, cid: str):
        """Get details of a specific contest"""
        args = base_request_parser.parse_args()
        user = get_api_user(args)

        dat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if dat is None:
            server.custom_abort(404, f"Contest not found.")
        can_edit = contests.check_super_access(dat, user)
        if not can_edit and dat.hidden:
            server.custom_abort(404, "Contest not found")

        status, _, can_see_problems = contests.check_status(dat, user)
        can_see_problems = can_see_problems or can_edit
        info = dat.datas

        announcements_data = [{
            "title": a.title, "content": a.content, "time": a.time.timestamp()
        } for a in reversed(dat.announcements.filter_by(public=True, question=False).all())]

        questions_query = dat.announcements.filter_by(question=True)
        if not can_edit:
            questions_query = questions_query.filter_by(user=user.data)
        questions_data = [{
            "id": q.id, "title": q.title, "content": q.content,
            "time": q.time.timestamp(), "author": q.user.username,
            "answer": q.answer
        } for q in reversed(questions_query.all())]

        return api_response({
            "cid": dat.cid,
            "name": dat.name,
            "description": "a contest",
            "start_time": info.start,
            "end_time": info.start + info.elapsed * 60,
            "elapsed": info.elapsed,
            "status": status.name,
            "can_edit": can_edit,
            "can_see_problems": can_see_problems,
            "problems": [{"pid": pid, "name": p.name} for pid, p in info.problems.items()],
            "announcements": announcements_data,
            "questions": questions_data,
            "is_registered": user.is_authenticated and user.id in info.participants,
            "is_virtual_participant": user.is_authenticated and user.id in info.virtual_participants,
            "can_register": info.can_register and user.is_authenticated,
        })


@ns.route("/<string:cid>/status")
@ns.param("cid", "The contest ID")
class ContestStatus(Resource):
    @ns.doc("get_contest_status")
    @ns.expect(contest_status_input)
    @marshal_with(ns, contest_status_output)
    def get(self, cid: str):
        """Get submission status for a contest with filtering"""
        args = contest_status_input.parse_args()
        api_user = get_api_user(args)

        dat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if dat is None:
            server.custom_abort(404, f"Contest not found.")
        can_edit = contests.check_super_access(dat, api_user)
        if not can_edit and dat.hidden:
            server.custom_abort(404, "Contest not found")
        info = dat.datas
        status_query = dat.submissions

        if args["user"]:
            user_filter: datas.User = datas.first(datas.User, username=args["user"])
            if user_filter is None:
                server.custom_abort(404, "User not found")
            status_query = status_query.filter_by(user=user_filter)
        if args["pid"]:
            if args["pid"] not in info.problems:
                server.custom_abort(404, "Problem not found in contest")
            status_query = status_query.filter_by(pid=info.problems[args["pid"]].pid)
        if args["result"] and args["result"] in objs.TaskResult.__members__:
            status_query = status_query.filter_by(simple_result_flag=objs.TaskResult[args["result"]].name)
        if args["lang"] and args["lang"] in executing.langs:
            status_query = status_query.filter_by(language=args["lang"])

        got_data, page_cnt, page_idx, show_pages = pagination(status_query, args)
        out = []
        can_edit = contests.check_super_access(dat, api_user)

        for obj in got_data:
            obj: datas.Submission
            problem_display_id = next((k for k, v in info.problems.items() if v.pid == obj.pid), "?")
            problem_name = info.problems[problem_display_id].name if problem_display_id != "?" else "???"

            can_see_details = api_user.is_authenticated and (
                    api_user.has(Permission.admin) or api_user.id == obj.user.username)
            can_know_all = can_see_details or info.standing.public or can_edit

            if can_know_all:
                out.append({
                    "id": str(obj.id), "time": obj.time.timestamp(), "user_id": obj.user.username,
                    "user_name": obj.user.display_name, "problem_id": problem_display_id, "problem_name": problem_name,
                    "lang": obj.language, "result": obj.simple_result or "unknown",
                    "can_see": can_see_details
                })
            else:
                out.append({
                    "id": str(obj.id), "time": obj.time.timestamp(), "user_id": "???", "user_name": "???",
                    "problem_id": "?", "problem_name": "???", "lang": "???", "result": "???",
                    "can_see": False
                })

        return api_response({
            "data": out, "page": page_idx, "page_count": page_cnt, "show_pages": show_pages,
        })


@ns.route("/<string:cid>/register")
@ns.param("cid", "The contest ID")
class ContestRegister(Resource):
    @ns.doc("register_for_contest")
    @ns.expect(base_request_parser)
    @marshal_with(ns, ok_output)
    def post(self, cid: str):
        """Register for a contest"""
        args = base_request_parser.parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            server.custom_abort(403, "Authentication required to register")

        dat = datas.first(datas.Contest, cid=cid)
        if dat is None:
            server.custom_abort(404, "Contest not found")
        per = datas.get_by_id(datas.Period, dat.main_period_id)
        if per is None:
            server.custom_abort(500, "Contest main period data is missing")
        info = dat.datas
        if not info.can_register or per.is_over():
            server.custom_abort(403, "Registration is not open")
        if user.id in info.participants:
            server.custom_abort(409, "User already registered")

        info.participants.append(user.id)
        dat.datas = info
        flag_modified(dat, "data")
        datas.add(dat)
        return api_response({"message": "Successfully registered"})


@ns.route("/<string:cid>/unregister")
@ns.param("cid", "The contest ID")
class ContestUnregister(Resource):
    @ns.doc("unregister_from_contest")
    @ns.expect(base_request_parser)
    @marshal_with(ns, ok_output)
    def post(self, cid: str):
        """Unregister from a contest"""
        args = base_request_parser.parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            server.custom_abort(403, "Authentication required")

        dat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if dat is None:
            server.custom_abort(404, "Contest not found")
        info = dat.datas
        if not info.can_register:
            server.custom_abort(403, "Cannot unregister from this contest")
        if user.id not in info.participants:
            server.custom_abort(409, "User is not registered")

        info.participants.remove(user.id)
        dat.datas = info
        flag_modified(dat, "data")
        datas.add(dat)
        return api_response({"message": "Successfully unregistered"})


@ns.route("/<string:cid>/virtual")
@ns.param("cid", "The contest ID")
class ContestVirtual(Resource):
    @ns.doc("register_virtual_contest")
    @ns.expect(virtual_register_input)
    @marshal_with(ns, ok_output)
    def post(self, cid: str):
        """Register for a virtual contest"""
        args = virtual_register_input.parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            server.custom_abort(403, "Authentication required")

        dat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if dat is None:
            server.custom_abort(404, "Contest not found")
        info = dat.datas
        if not dat.can_virtual():
            server.custom_abort(403, "This contest does not support virtual participation")
        if user.id in info.virtual_participants:
            server.custom_abort(409, "User already registered for a virtual contest")

        start_time: datetime = tools.to_datetime(args["start_time"], second=0, microsecond=0)
        per = datas.Period.query.filter_by(start_time=start_time, contest=dat, is_virtual=True).first()
        if per:
            idx = per.id
        else:
            nw_per = datas.Period(
                start_time=start_time,
                end_time=start_time + timedelta(minutes=info.elapsed),
                contest=dat,
                is_virtual=True
            )
            datas.add(nw_per)
            datas.flush()
            idx = nw_per.id

        info.virtual_participants[user.id] = idx
        flag_modified(dat, "data")
        datas.add(dat)
        return api_response({"message": "Successfully registered for virtual contest"})


@ns.route("/<string:cid>/standing")
@ns.param("cid", "The contest ID")
class ContestStanding(Resource):
    @ns.doc("get_contest_standing")
    @ns.expect(base_request_parser)
    @marshal_with(ns, standing_output)
    def get(self, cid: str):
        """Get contest standings (scoreboard)"""
        args = base_request_parser.parse_args()
        user = get_api_user(args)
        cdat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if cdat is None:
            server.custom_abort(404, "Contest not found")
        can_edit = contests.check_super_access(cdat, user)
        if not can_edit and cdat.hidden:
            server.custom_abort(404, "Contest not found")
        info = cdat.datas
        dt = time.time() - info.start
        dt = dt / 60 - info.elapsed
        can_see = (info.standing.public and (dt <= -info.standing.start_freeze or dt >= info.standing.end_freeze))
        if not can_see and not contests.check_super_access(cdat, user):
            server.custom_abort(403, "Standings are not public at this time")
        dat = contests.get_standing(cid)
        return api_response(dat)


@ns.route("/<string:cid>/questions")
@ns.param("cid", "The contest ID")
class ContestQuestion(Resource):
    @ns.doc("ask_question")
    @ns.expect(question_input)
    @marshal_with(ns, ok_output)
    def post(self, cid: str):
        """Ask a question in a contest"""
        args = question_input.parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            server.custom_abort(403, "Authentication required")

        cdat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if cdat is None:
            server.custom_abort(404, "Contest not found")
        if len(args["title"]) > 80 or len(args["content"]) > 1000:
            server.custom_abort(400, "Title or content too long")

        obj = datas.Announcement(
            time=datetime.now(),
            title=args["title"],
            content=args["content"],
            user=user.data,
            contest=cdat,
            public=False,
            question=True
        )
        datas.add(obj)
        return api_response({"message": "Question submitted successfully"})


@ns.route("/<string:cid>/submissions/<int:sub_id>/reject")
@ns.param("cid", "The contest ID")
@ns.param("sub_id", "The submission ID")
class RejectSubmission(Resource):
    @ns.doc("reject_submission")
    @ns.expect(base_request_parser)
    @marshal_with(ns, ok_output)
    def post(self, cid: str, sub_id: int):
        """Reject a submission in a contest (requires admin/owner)"""
        args = base_request_parser.parse_args()
        user = get_api_user(args)

        cdat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if cdat is None:
            server.custom_abort(404, "Contest not found")
        if not contests.check_super_access(cdat, user):
            server.custom_abort(403, "Permission denied to reject submission")

        dat = datas.get_by_id(datas.Submission, sub_id)
        if dat is None:
            server.custom_abort(404, "Submission not found")
        if dat.contest_id != cdat.id:
            server.custom_abort(400, "Submission does not belong to this contest")
        if not dat.completed:
            server.custom_abort(400, "Cannot reject an incomplete submission")

        contests.reject(dat)
        datas.add(dat)
        return api_response({"message": "Submission rejected"})


@ns.route("/<string:cid>/problem/<string:pid>")
@ns.param("cid", "The contest ID")
@ns.param("pid", "The problem ID within the contest")
class ContestProblem(Resource):
    @ns.doc("get_contest_problem")
    @marshal_with(ns, contest_problem_detail_model)
    def get(self, cid: str, pid: str):
        """Get details of a specific problem in a contest"""
        args = base_request_parser.parse_args()
        user = get_api_user(args)

        cdat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if cdat is None:
            server.custom_abort(404, "Contest not found")
        can_edit = contests.check_super_access(cdat, user)
        status, _, can_see_problems = contests.check_status(cdat, user)

        if not (can_edit or can_see_problems):
            server.custom_abort(403, "You do not have access to this contest's problems yet")

        info = cdat.datas
        if pid not in info.problems:
            server.custom_abort(404, "Problem not found in this contest")

        problem_internal_pid = info.problems[pid].pid
        pdat: datas.Problem = datas.first(datas.Problem, pid=problem_internal_pid)
        if pdat is None:
            server.custom_abort(500, "Problem data is missing")
        p_info = pdat.datas

        langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
        path = constants.problem_path / pdat.pid
        statement = tools.read(path / "statement.md") if (path / "statement.md").is_file() else ""
        statement_html = tools.read(path / "statement.html") if (path / "statement.html").is_file() else ""
        dat = pdat.datas
        samples = dat.manual_samples
        samples.extend([objs.ManualSample(tools.read(path / "testcases" / o.in_file),
                                          tools.read(path / "testcases" / o.out_file))
                        for o in dat.testcases if o.sample])
        samples.extend([objs.ManualSample(tools.read(path / "testcases_gen" / o.in_file),
                                          tools.read(path / "testcases_gen" / o.out_file))
                        for o in dat.testcases_gen if o.sample])

        problem_data = {
            "pid": pid,
            "internal_pid": pdat.pid,
            "name": p_info.name,
            "description": "a problem",
            "allowed_languages": langs,
            "contest_cid": cid,
            "contest_name": cdat.name,
            "time_limit": p_info.timelimit,
            "memory_limit": p_info.memorylimit,
            "statement": statement,
            "statement_html": statement_html,
            "samples": [{"input": o.in_txt, "output": o.out_txt} for o in samples],
        }

        return api_response(problem_data)
