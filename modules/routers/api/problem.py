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
from flask_restx import Resource, fields, abort

from .base import get_api_user, api_response, api, marshal_with, request_parser, Form, File, paging, pagination
from ... import objs, problemsetting, datas, executing, constants, tools

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
        user = get_api_user(args, objs.Permission.admin)
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
        user = get_api_user(args)
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


problem_detail_get_input = request_parser()
problem_detail_get_output = ns.model("ProblemDetailOutput", {
    "pid": fields.String(description="Problem ID"),
    "title": fields.String(description="Title of the problem"),
    "statement": fields.String(description="Problem statement in HTML format"),
    "langs": fields.List(fields.String, description="List of programming languages allowed for this problem"),
    "samples": fields.List(fields.Nested(ns.model("SampleTestcase", {
            "input": fields.String(description="Sample input for the problem"),
            "output": fields.String(description="Sample output for the problem")
    })), description="List of sample testcases"),
    "default_code": fields.Raw(description="Default code for each language"),
    "time_limit": fields.Integer(description="Time limit for the problem in milliseconds"),
    "memory_limit": fields.Integer(description="Memory limit for the problem in megabytes")
})


@ns.route("/<string:pid>")
class ProblemDetail(Resource):
    @ns.doc("get_problem")
    @ns.expect(problem_detail_get_input)
    @marshal_with(ns, problem_detail_get_output)
    def get(self, pid):
        args = problem_detail_get_input.parse_args()
        user = get_api_user(args)
        pdat = datas.first_or_404(datas.Problem, pid=pid)
        dat = pdat.datas
        if not pdat.is_public and not user.has(objs.Permission.admin) and user.id not in dat.users:
            abort(403)
        langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
        path = constants.problem_path / pid
        statement = tools.read(path / "statement.html")
        samples = dat.manual_samples
        default_code = dat.default_code
        files = {f for f in default_code.values() if f and f.strip()}
        content_map = {}
        for f in files:
            content_map[f] = (path / "file" / f).open(encoding="utf-8").read()
        default_code = {k: content_map.get(v, "") for k, v in default_code.items()}
        samples.extend([objs.ManualSample(tools.read(path / "testcases" / o.in_file),
                                          tools.read(path / "testcases" / o.out_file))
                        for o in dat.testcases if o.sample])
        samples.extend([objs.ManualSample(tools.read(path / "testcases_gen" / o.in_file),
                                          tools.read(path / "testcases_gen" / o.out_file))
                        for o in dat.testcases_gen if o.sample])
        res = {
            "pid": pid,
            "title": dat.name,
            "statement": statement,
            "langs": langs,
            "samples": [{"input": o.in_txt, "output": o.out_txt} for o in samples],
            "default_code": default_code,
            "time_limit": dat.timelimit,
            "memory_limit": dat.memorylimit
        }
        return api_response(res)
