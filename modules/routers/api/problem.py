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
from flask_restx import Resource, fields

from .base import get_api_user, api_response, api, marshal_with, request_parser, Form, File, paging, pagination
from ... import objs, problemsetting, datas

ns = api.namespace("problem", path="/problem", description="Problem-related API endpoints")

problem_post_input = request_parser(
    Form("name", "Title of the problem"),
    Form("pid", "Target pid of the problem", required=False),
    File("zip_file", "Content of the problem in zip file", required=False)
)
problem_post_output = ns.model("CreateProblemOutput", {
    "pid": fields.String(description="ID of the problem created")
})
problem_get_input = request_parser(*paging())
problem_get_output = ns.model("ProblemListOutput", {
    "page_count": fields.Integer(description="Total number of pages"),
    "page": fields.Integer(description="Current page index"),
    "results": fields.List(fields.Nested(ns.model("ProblemOutput", {
        "pid": fields.String(description="Problem ID"),
        "name": fields.String(description="Problem name")
    })), description="List of problems")
})


@ns.route("")
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

    @ns.doc("list_problems")
    @ns.expect(problem_get_input)
    @marshal_with(ns, problem_get_output)
    def get(self):
        args = problem_get_input.parse_args()
        public_problems = datas.filter_by(datas.Problem, is_public=True)
        got_data, page_cnt, page_idx, show_pages = pagination(public_problems, args)
        results = [
            {
                "pid": problem.pid,
                "name": problem.name,
            }
            for problem in got_data
        ]
        res = {
            "page_count": page_cnt,
            "page": page_idx,
            "results": results
        }
        return api_response(res)
