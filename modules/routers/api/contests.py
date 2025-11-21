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

from flask_restx import Resource, fields, abort
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
)
from ... import contests, datas, executing, objs, tools, constants
from ...objs import Permission

ns = api.namespace("contests", path="/contests", description="Contest related API endpoints")

# endregion

# region Models
contest_summary_model = ns.model("ContestSummary", {
    "cid": fields.String(description="Contest ID"),
    "name": fields.String(description="Contest Name"),
    "start_time": fields.Float(description="Start time timestamp"),
    "end_time": fields.Float(description="End time timestamp"),
    "status": fields.String(description="Contest status (Running, Upcoming, Ended)"),
    "can_virtual": fields.Boolean(description="Whether virtual participation is allowed")
})
contest_list_output = ns.model("ContestListOutput", {
    "contests": fields.List(fields.Nested(contest_summary_model)),
    "page": fields.Integer,
    "page_count": fields.Integer,
    "show_pages": fields.List(fields.Integer),
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
    "title": fields.String,
    "content": fields.String,
    "time": fields.Float,
})
question_model = ns.model("Question", {
    "id": fields.Integer,
    "title": fields.String,
    "content": fields.String,
    "time": fields.Float,
    "author": fields.String,
    "answer": fields.String(description="Content of the reply to this question, if any"),
})
contest_details_output = ns.model("ContestDetailsOutput", {
    "cid": fields.String,
    "name": fields.String,
    "description": fields.String,
    "start_time": fields.Float,
    "end_time": fields.Float,
    "status": fields.String,
    "can_edit": fields.Boolean,
    "can_see_problems": fields.Boolean,
    "problems": fields.List(fields.Nested(problem_in_contest_model)),
    "announcements": fields.List(fields.Nested(announcement_model)),
    "questions": fields.List(fields.Nested(question_model)),
    "is_registered": fields.Boolean,
    "is_virtual_participant": fields.Boolean,
})
submission_status_model = ns.model("SubmissionStatus", {
    "id": fields.String,
    "timestamp": fields.Float,
    "user_id": fields.String,
    "user_name": fields.String,
    "problem_id": fields.String,
    "problem_name": fields.String,
    "language": fields.String,
    "result": fields.String,
    "can_see_details": fields.Boolean,
})
contest_status_output = ns.model("ContestStatusOutput", {
    "submissions": fields.List(fields.Nested(submission_status_model)),
    "page": fields.Integer,
    "page_count": fields.Integer,
    "show_pages": fields.List(fields.Integer),
})
standing_output = ns.model("StandingOutput", {
    "headers": fields.List(fields.Raw),
    "standings": fields.List(fields.Raw)
})
contest_problem_detail_model = ns.model("ContestProblemDetail", {
    "pid": fields.String(description="Problem ID within the contest"),
    "internal_pid": fields.String(description="System-wide Problem ID"),
    "name": fields.String,
    "description": fields.String(description="Problem description HTML"),
    "allowed_languages": fields.List(fields.String),
    "contest_cid": fields.String,
    "contest_name": fields.String,
    "time_limit": fields.Float,
    "memory_limit": fields.Integer,
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

@ns.route("/")
class ContestList(Resource):
    @ns.doc("list_contests")
    @ns.expect(contest_list_input)
    @marshal_with(ns, contest_list_output)
    def get(self):
        """List all available contests"""
        args = contest_list_input.parse_args()
        user = get_api_user(args)

        query = datas.Contest.query
        if not user.has(Permission.admin):
            query = query.filter_by(hidden=False)

        got_data, page_cnt, page_idx, show_pages = pagination(query, args)

        contests_data = []
        for contest in got_data:
            info: objs.ContestData = contest.datas
            status, _, _ = contests.check_status(contest, user)
            contests_data.append({
                "cid": contest.cid,
                "name": contest.name,
                "start_time": info.start,
                "end_time": info.start + info.elapsed * 60,
                "status": status.name,
                "can_virtual": contest.can_virtual()
            })

        return api_response({
            "contests": contests_data,
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
            abort(400, "Invalid contest name length")
        cid = contests.create_contest(name, user.data)
        return api_response({"contest_id": cid})


@ns.route("/<string:cid>")
@ns.param("cid", "The contest ID")
class Contest(Resource):
    @ns.doc("get_contest_details")
    @marshal_with(ns, contest_details_output)
    def get(self, cid: str):
        """Get details of a specific contest"""
        args = request_parser().parse_args()
        user = get_api_user(args)

        dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        can_edit = contests.check_super_access(dat, user)
        if not can_edit and dat.hidden:
            abort(404, "Contest not found")

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
            "status": status.name,
            "can_edit": can_edit,
            "can_see_problems": can_see_problems,
            "problems": [{"pid": pid, "name": p.name} for pid, p in info.problems.items()],
            "announcements": announcements_data,
            "questions": questions_data,
            "is_registered": user.is_authenticated and user.id in info.participants,
            "is_virtual_participant": user.is_authenticated and user.id in info.virtual_participants
        })


@ns.route("/<string:cid>/status")
@ns.param("cid", "The contest ID")
class ContestStatus(Resource):
    @ns.doc("get_contest_status")
    @ns.expect(contest_status_input)
    @marshal_with(ns, contest_status_output)
    def post(self, cid: str):
        """Get submission status for a contest with filtering"""
        args = contest_status_input.parse_args()
        api_user = get_api_user(args)

        dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        info = dat.datas
        status_query = dat.submissions

        if args["user"]:
            user_filter: datas.User = datas.first_or_404(datas.User, username=args["user"])
            status_query = status_query.filter_by(user=user_filter)
        if args["pid"]:
            if args["pid"] not in info.problems:
                abort(404, "Problem not found in contest")
            status_query = status_query.filter_by(pid=info.problems[args["pid"]].pid)
        if args["result"] and args["result"] in objs.TaskResult.__members__:
            status_query = status_query.filter_by(simple_result_flag=objs.TaskResult[args["result"]].name)
        if args["lang"] and args["lang"] in executing.langs:
            status_query = status_query.filter_by(language=args["lang"])

        got_data, page_cnt, page_idx, show_pages = tools.pagination(status_query, True, args["page"], args["page_size"])
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
                    "id": str(obj.id), "timestamp": obj.time.timestamp(), "user_id": obj.user.username,
                    "user_name": obj.user.display_name, "problem_id": problem_display_id, "problem_name": problem_name,
                    "language": obj.language, "result": obj.simple_result or "unknown",
                    "can_see_details": can_see_details
                })
            else:
                out.append({
                    "id": str(obj.id), "timestamp": obj.time.timestamp(), "user_id": "???", "user_name": "???",
                    "problem_id": "?", "problem_name": "???", "language": "???", "result": "???",
                    "can_see_details": False
                })

        return api_response({
            "submissions": out, "page": page_idx, "page_count": page_cnt, "show_pages": show_pages,
        })


@ns.route("/<string:cid>/register")
@ns.param("cid", "The contest ID")
class ContestRegister(Resource):
    @ns.doc("register_for_contest")
    @marshal_with(ns, ok_output)
    def post(self, cid: str):
        """Register for a contest"""
        args = request_parser().parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            abort(403, "Authentication required to register")

        dat = datas.first_or_404(datas.Contest, cid=cid)
        per = datas.get_or_404(datas.Period, dat.main_period_id)
        info = dat.datas
        if not info.can_register or per.is_over():
            abort(403, "Registration is not open")
        if user.id in info.participants:
            abort(409, "User already registered")

        info.participants.append(user.id)
        dat.datas = info
        flag_modified(dat, "data")
        datas.add(dat)
        return api_response({"message": "Successfully registered"})


@ns.route("/<string:cid>/unregister")
@ns.param("cid", "The contest ID")
class ContestUnregister(Resource):
    @ns.doc("unregister_from_contest")
    @marshal_with(ns, ok_output)
    def post(self, cid: str):
        """Unregister from a contest"""
        args = request_parser().parse_args()
        user = get_api_user(args)
        if not user.is_authenticated:
            abort(403, "Authentication required")

        dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        info = dat.datas
        if not info.can_register:
            abort(403, "Cannot unregister from this contest")
        if user.id not in info.participants:
            abort(409, "User is not registered")

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
            abort(403, "Authentication required")

        dat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        info = dat.datas
        if not dat.can_virtual():
            abort(403, "This contest does not support virtual participation")
        if user.id in info.virtual_participants:
            abort(409, "User already registered for a virtual contest")

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
    @marshal_with(ns, standing_output)
    def get(self, cid: str):
        """Get contest standings (scoreboard)"""
        args = request_parser().parse_args()
        user = get_api_user(args)
        cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        info = cdat.datas
        dt = time.time() - info.start
        dt = dt / 60 - info.elapsed
        can_see = (info.standing.public and (dt <= -info.standing.start_freeze or dt >= info.standing.end_freeze))
        if not can_see and not contests.check_super_access(cdat, user):
            abort(403, "Standings are not public at this time")
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
            abort(403, "Authentication required")

        cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        if len(args["title"]) > 80 or len(args["content"]) > 1000:
            abort(400, "Title or content too long")

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
    @marshal_with(ns, ok_output)
    def post(self, cid: str, sub_id: int):
        """Reject a submission in a contest (requires admin/owner)"""
        args = request_parser().parse_args()
        user = get_api_user(args)

        cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        if not contests.check_super_access(cdat, user):
            abort(403, "Permission denied to reject submission")

        dat = datas.get_or_404(datas.Submission, sub_id)
        if dat.contest_id != cdat.id:
            abort(400, "Submission does not belong to this contest")
        if not dat.completed:
            abort(400, "Cannot reject an incomplete submission")

        contests.reject(dat)
        datas.add(dat)
        return api_response({"message": "Submission rejected"})


@ns.route("/<string:cid>/problems/<string:pid>")
@ns.param("cid", "The contest ID")
@ns.param("pid", "The problem ID within the contest")
class ContestProblem(Resource):
    @ns.doc("get_contest_problem")
    @marshal_with(ns, contest_problem_detail_model)
    def get(self, cid: str, pid: str):
        """Get details of a specific problem in a contest"""
        args = request_parser().parse_args()
        user = get_api_user(args)

        cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        can_edit = contests.check_super_access(cdat, user)
        status, _, can_see_problems = contests.check_status(cdat, user)

        if not (can_edit or can_see_problems):
            abort(403, "You do not have access to this contest's problems yet")

        info = cdat.datas
        if pid not in info.problems:
            abort(404, "Problem not found in this contest")

        problem_internal_pid = info.problems[pid].pid
        pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=problem_internal_pid)
        p_info = pdat.datas

        langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]

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
        }

        return api_response(problem_data)
