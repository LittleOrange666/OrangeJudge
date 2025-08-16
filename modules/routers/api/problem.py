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

from flask import request
from flask_restx import Resource, fields, reqparse

from .base import get_api_user, api_response, api, marshal_with
from ... import objs, problemsetting

ns = api.namespace("problem", path="/problem", description="Problem-related API endpoints")

problem_post_input = reqparse.RequestParser()
problem_post_input.add_argument("username", type=str, required=True,
                                   help="Username of the user submitting the problem")
problem_post_input.add_argument("name", type=str, required=True, help="Title of the problem")
problem_post_input.add_argument("pid", type=str, required=False, help="Target pid of the problem")
problem_post_input.add_argument("zip_file", type=lambda x: x, required=False,
                                   help="content of the problem in zip file", location="files")
problem_post_output = ns.model("SubmissionOutput", {
    "pid": fields.String(description="ID of the problem created")
})


@ns.route("/")
class ProblemIndex(Resource):
    @ns.doc("create_problem")
    @ns.expect(problem_post_input)
    @marshal_with(ns, problem_post_output)
    def post(self):
        args = problem_post_input.parse_args()
        user = get_api_user(args["username"], objs.Permission.admin)
        pid = args.get("pid", "")
        name = args["name"]
        idx = problemsetting.create_problem(name, pid, user.data)
        res = {"pid": idx}
        if args.get("zip_file"):
            with problemsetting.Problem(idx) as problem:
                problemsetting.import_problem(request.form, problem)
                problemsetting.create_version({
                    "description": "Initial version"
                }, problem)
        return api_response(res)
