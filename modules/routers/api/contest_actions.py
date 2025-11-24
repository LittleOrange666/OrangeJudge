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

from .base import get_api_user, api_response, api, request_parser, Form, File, base_request_parser
from ... import contests, datas, server

ns = api.namespace("contest_manage", path="/contest/<string:cid>/manage",
                   description="Contest management API endpoints")


def do_action(cid: str, action_name: str, action_input):
    auth_args = action_input.parse_args()
    user = get_api_user(auth_args)
    cdat: datas.Contest = datas.first(datas.Contest, cid=cid)
    if cdat is None:
        server.custom_abort(404, "Contest not found.")
    if not contests.check_super_access(cdat, user):
        server.custom_abort(403, "You do not have permission to perform this action on this contest.")

    action_func = contests.actions.get(action_name)

    if not action_func:
        server.custom_abort(501, f"Action handler for '{action_name}' is not implemented.")

    dat = cdat.datas

    result = action_func(request.form, cdat, dat)
    cdat.datas = dat
    datas.add(cdat)
    if action_name == "change_settings":
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

    server.custom_abort(500, f"Action handler for '{action_name}' returned an unexpected result.")


@ns.route("/problem")
class Problem(Resource):
    post_action_name = "add_problem"
    post_action_input = request_parser(
        Form("pid", "Problem ID to add", str, required=False)
    )
    delete_action_name = "remove_problem"
    delete_action_input = request_parser(
        Form("idx", "Problem Index to remove", str, required=True)
    )
    put_action_name = "save_order"
    put_action_input = request_parser(
        Form("order", "New order of problem indices, comma-separated", str, required=True)
    )

    @ns.doc("contest_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, cid: str):
        """Add a problem to the contest."""
        return do_action(cid, self.post_action_name, self.post_action_input)

    @ns.doc("contest_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, cid: str):
        """Remove a problem from the contest."""
        return do_action(cid, self.delete_action_name, self.delete_action_input)

    @ns.doc("contest_" + put_action_name)
    @ns.expect(put_action_input)
    def put(self, cid: str):
        """Save the order of problems in the contest."""
        return do_action(cid, self.put_action_name, self.put_action_input)


@ns.route("/participant")
class Participant(Resource):
    post_action_name = "add_participant"
    post_action_input = request_parser(
        Form("username", "Username to add", str, required=False),
        File("file", "File containing list of usernames to add", required=False)
    )
    delete_action_name = "remove_participant"
    delete_action_input = request_parser(
        Form("username", "Username to remove", str, required=True)
    )

    @ns.doc("contest_" + post_action_name, description="Add a participant by username or upload a file containing "
                                                       "multiple usernames (.csv or .xlsx).")
    @ns.expect(post_action_input)
    def post(self, cid: str):
        """Add a participant or multiple participants to the contest."""
        res = self.post_action_input.parse_args()
        if not res.get("username") and not res.get("file"):
            server.custom_abort(400, "Either 'username' or 'file' must be provided.")
        if res.get("username") and res.get("file"):
            server.custom_abort(400, "Only one of 'username' or 'file' should be provided.")
        action_name = self.post_action_name + ("s" if res.get("file") else "")
        return do_action(cid, action_name, self.post_action_input)

    @ns.doc("contest_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, cid: str):
        """Remove a participant from the contest."""
        return do_action(cid, self.delete_action_name, self.delete_action_input)


@ns.route("/settings")
class ChangeSettings(Resource):
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
    def put(self, cid: str):
        """Change contest settings."""
        return do_action(cid, self.action_name, self.action_input)


@ns.route("/announcement")
class Announcement(Resource):
    post_action_name = "send_announcement"
    post_action_input = request_parser(
        Form("title", "Title of the announcement", str, required=True),
        Form("content", "Content of the announcement", str, required=True)
    )
    delete_action_name = "remove_announcement"
    delete_action_input = request_parser(
        Form("id", "ID of the announcement to remove", int, required=True)
    )
    put_action_name = "save_question"
    put_action_input = request_parser(
        Form("id", "ID of the question to reply to", int, required=True),
        Form("content", "Reply content", str, required=True),
        Form("public", "Whether the reply is public", str, required=True, choices=["no", "yes"])
    )

    @ns.doc("contest_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, cid: str):
        """Send an announcement to all contest participants."""
        return do_action(cid, self.post_action_name, self.post_action_input)

    @ns.doc("contest_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, cid: str):
        """Remove an announcement from the contest."""
        return do_action(cid, self.delete_action_name, self.delete_action_input)

    @ns.doc("contest_" + put_action_name)
    @ns.expect(put_action_input)
    def put(self, cid: str):
        """Reply a question asked by a participant."""
        return do_action(cid, self.put_action_name, self.put_action_input)
