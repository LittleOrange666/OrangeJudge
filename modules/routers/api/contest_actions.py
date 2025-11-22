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
from flask_login import current_user, login_user, logout_user
from flask_restx import Resource, abort

from .base import get_api_user, api_response, api, request_parser
from ... import contests, datas


ns = api.namespace("contest_actions", path="/contest/<string:cid>/manage/actions",
                   description="Detailed contest management actions")


class BaseContestAction(Resource):
    action_name = ""

    def post(self, cid: str):
        auth_args = request_parser().parse_args()
        user = get_api_user(auth_args)
        cdat: datas.Contest = datas.first_or_404(datas.Contest, cid=cid)
        if not contests.check_super_access(cdat, user):
            abort(403, "You do not have permission to perform this action on this contest.")

        action_func = contests.actions.get(self.action_name)

        if not action_func:
            abort(501, f"Action handler for '{self.action_name}' is not implemented.")

        dat = cdat.datas

        result = action_func(request.form, cdat, dat)

        if isinstance(result, str):
            return api_response({"message": "OK", "view_hint": result})
        elif isinstance(result, Response):
            return result
        elif result is None:
            return api_response({"message": "OK"})

        abort(500, f"Action handler for '{self.action_name}' returned an unexpected result.")


@ns.route("/add_problem")
class AddProblem(BaseContestAction):
    action_name = "add_problem"


@ns.route("/remove_problem")
class RemoveProblem(BaseContestAction):
    action_name = "remove_problem"


@ns.route("/add_participant")
class AddParticipant(BaseContestAction):
    action_name = "add_participant"


@ns.route("/add_participants")
class AddParticipants(BaseContestAction):
    action_name = "add_participants"


@ns.route("/remove_participant")
class RemoveParticipant(BaseContestAction):
    action_name = "remove_participant"


@ns.route("/change_settings")
class ChangeSettings(BaseContestAction):
    action_name = "change_settings"


@ns.route("/save_order")
class SaveOrder(BaseContestAction):
    action_name = "save_order"


@ns.route("/send_announcement")
class SendAnnouncement(BaseContestAction):
    action_name = "send_announcement"


@ns.route("/remove_announcement")
class RemoveAnnouncement(BaseContestAction):
    action_name = "remove_announcement"


@ns.route("/save_question")
class SaveQuestion(BaseContestAction):
    action_name = "save_question"