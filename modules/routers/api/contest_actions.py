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
from datetime import timedelta

from flask import request, Response
from flask_restx import Resource

from .base import get_api_user, api_response, api, request_parser, Form, File
from ... import contests, datas, server

ns = api.namespace("contest_actions", path="/contest/<string:cid>/manage",
                   description="Detailed contest management actions")


class BaseContestAction(Resource):
    action_name = ""
    action_input = request_parser()

    def do_post(self, cid: str):
        auth_args = self.action_input.parse_args()
        user = get_api_user(auth_args)
        cdat: datas.Contest = datas.first(datas.Contest, cid=cid)
        if cdat is None:
            server.custom_abort(404, "Contest not found.")
        if not contests.check_super_access(cdat, user):
            server.custom_abort(403, "You do not have permission to perform this action on this contest.")

        action_func = contests.actions.get(self.action_name)

        if not action_func:
            server.custom_abort(501, f"Action handler for '{self.action_name}' is not implemented.")

        dat = cdat.datas

        result = action_func(request.form, cdat, dat)
        cdat.datas = dat
        datas.add(cdat)
        if self.action_name == "change_settings":
            for the_per in cdat.periods:
                the_per: datas.Period
                the_per.end_time = the_per.start_time + timedelta(minutes=dat.elapsed)
            datas.add(*cdat.periods)

        if isinstance(result, str):
            return api_response({"message": "OK", "view_hint": result})
        elif isinstance(result, Response):
            return result
        elif result is None:
            return api_response({"message": "OK"})

        server.custom_abort(500, f"Action handler for '{self.action_name}' returned an unexpected result.")


@ns.route("/add_problem")
class AddProblem(BaseContestAction):
    action_name = "add_problem"
    action_input = request_parser(
        Form("pid", "Problem ID to add", str, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Add a problem to the contest."""
        return self.do_post(cid)


@ns.route("/remove_problem")
class RemoveProblem(BaseContestAction):
    action_name = "remove_problem"
    action_input = request_parser(
        Form("idx", "Problem Index to remove", str, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Remove a problem from the contest."""
        return self.do_post(cid)


@ns.route("/add_participant")
class AddParticipant(BaseContestAction):
    action_name = "add_participant"
    action_input = request_parser(
        Form("username", "Username to add", str, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Add a participant to the contest."""
        return self.do_post(cid)


@ns.route("/add_participants")
class AddParticipants(BaseContestAction):
    action_name = "add_participants"
    action_input = request_parser(
        File("file", "File containing list of usernames to add", required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Add multiple participants to the contest."""
        return self.do_post(cid)


@ns.route("/remove_participant")
class RemoveParticipant(BaseContestAction):
    action_name = "remove_participant"
    action_input = request_parser(
        Form("username", "Username to remove", str, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Remove a participant from the contest."""
        return self.do_post(cid)


@ns.route("/change_settings")
class ChangeSettings(BaseContestAction):
    action_name = "change_settings"
    action_input = request_parser(
        Form("contest_title", "Title for the contest", str, required=True),
        Form("start_time", "Start time for the contest (ISO format)", str, required=True),
        Form("elapsed_time", "Elapsed time for the contest (in minutes)", int, required=True),
        Form("rule_type", "Rule type for the contest", str, required=True, choices=["icpc", "ioi"]),
        Form("pretest_type", "Pretest type for the contest", str, required=True, choices=["all", "last", "no"]),
        Form("practice_type", "Practice type for the contest", str, required=True, choices=["no", "private", "public"]),
        Form("register_type", "Whether self register is allowed", str, required=True, choices=["no", "yes"]),
        Form("show_standing", "Whether to show standings during the contest", str, required=True,
             choices=["no", "yes"]),
        Form("show_contest", "Whether to show the contest in the contest list", str, required=True,
             choices=["no", "yes"]),
        Form("freeze_time", "Freeze time before the end of the contest (in minutes)", int, required=True),
        Form("unfreeze_time", "Unfreeze time after the end of the contest (in minutes)", int, required=True),
        Form("penalty", "Penalty time for wrong submissions (in minutes)", int, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Change contest settings."""
        return self.do_post(cid)


@ns.route("/save_order")
class SaveOrder(BaseContestAction):
    action_name = "save_order"
    action_input = request_parser(
        Form("order", "New order of problem indices, comma-separated", str, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Save the order of problems in the contest."""
        return self.do_post(cid)


@ns.route("/send_announcement")
class SendAnnouncement(BaseContestAction):
    action_name = "send_announcement"
    action_input = request_parser(
        Form("title", "Title of the announcement", str, required=True),
        Form("content", "Content of the announcement", str, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Send an announcement to all contest participants."""
        return self.do_post(cid)


@ns.route("/remove_announcement")
class RemoveAnnouncement(BaseContestAction):
    action_name = "remove_announcement"
    action_input = request_parser(
        Form("id", "ID of the announcement to remove", int, required=True)
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """Remove an announcement from the contest."""
        return self.do_post(cid)


@ns.route("/save_question")
class SaveQuestion(BaseContestAction):
    action_name = "save_question"
    action_input = request_parser(
        Form("id", "ID of the question to reply to", int, required=True),
        Form("content", "Reply content", str, required=True),
        Form("public", "Whether the reply is public", str, required=True, choices=["no", "yes"])
    )

    @ns.doc("contest_" + action_name)
    @ns.expect(action_input)
    def post(self, cid: str):
        """reply a question asked by a participant."""
        return self.do_post(cid)
