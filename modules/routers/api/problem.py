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
import os

from flask import request
from flask_restx import Resource, fields, abort
from werkzeug.utils import secure_filename

from .base import get_api_user, api_response, api, marshal_with, request_parser, Form, paging, pagination, Args
from ... import objs, problemsetting, datas, executing, constants, tools, config, server
from ...constants import preparing_problem_path, problem_path

ns = api.namespace("problem", path="/problem", description="Problem-related API endpoints")

# region Models
problem_post_output = ns.model("CreateProblemOutput", {
    "pid": fields.String(description="ID of the problem created")
})
problem_list_result_item = ns.model("ProblemOutput", {
    "pid": fields.String(description="Problem ID"),
    "name": fields.String(description="Problem name")
})
problem_get_output = ns.model("ProblemListOutput", {
    "page_count": fields.Integer(description="Total number of pages"),
    "page": fields.Integer(description="Current page index"),
    "results": fields.List(fields.Nested(problem_list_result_item), description="List of problems")
})
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
version_info_model = ns.model("VersionInfo", {
    "version": fields.String(),
    "description": fields.String(),
    "create_time": fields.Float(),
})
manageable_problem_details_model = ns.model("ManageableProblemDetails", {
    "pid": fields.String(),
    "name": fields.String(),
    "is_public": fields.Boolean(),
    "data": fields.Raw(description="The full editable ProblemData object"),
    "versions": fields.List(fields.Nested(version_info_model)),
    "public_files": fields.List(fields.String),
    "default_checkers": fields.List(fields.String),
    "available_languages": fields.List(fields.String),
    "default_interactors": fields.List(fields.String),
    "collaborators": fields.List(fields.String),
    "current_actions": fields.List(fields.String, description="List of available background actions"),
    "background_action": fields.Raw(description="Current running background action, if any", required=False)
})
# endregion

# region Parsers
problem_post_input = request_parser(
    Form("name", "Title of the problem", required=True),
    Form("pid", "Target pid of the problem", required=False),
)
problem_get_input = request_parser(
    *paging(),
    Args("manageable", "List problems the user can manage", type=bool, required=False, default=False)
)
problem_detail_get_input = request_parser()
# endregion


@ns.route("")
class ProblemIndex(Resource):
    @ns.doc("create_problem")
    @ns.expect(problem_post_input)
    @marshal_with(ns, problem_post_output)
    def post(self):
        """Creates a new, empty problem."""
        args = problem_post_input.parse_args()
        user = get_api_user(args, objs.Permission.make_problems)
        pid = args.get("pid", "")
        name = args["name"]
        idx = problemsetting.create_problem(name, pid, user.data)
        res = {"pid": idx}
        return api_response(res)

    @ns.doc("list_problems")
    @ns.expect(problem_get_input)
    @marshal_with(ns, problem_get_output)
    def get(self):
        """Lists problems. Can list either public problems or problems the user can manage."""
        args = problem_get_input.parse_args()
        user = get_api_user(args)

        if args['manageable']:
            if not user.is_authenticated:
                abort(403, "Authentication required to list manageable problems.")

            if user.has(objs.Permission.admin):
                problem_obj = datas.Problem.query.filter(datas.Problem.pid != "test")
            elif user.has(objs.Permission.make_problems):
                problem_obj = user.data.problems.filter(datas.Problem.pid != "test")
            else:
                problem_obj = datas.Problem.query.filter(datas.Problem.id < 0)  # Empty query
        else:
            problem_obj = datas.Problem.query.filter_by(is_public=True)

        got_data, page_cnt, page_idx, _ = pagination(problem_obj, args)
        results = [{"pid": p.pid, "name": p.name} for p in got_data]
        res = {"page_count": page_cnt, "page": page_idx, "results": results}
        return api_response(res)


@ns.route("/<string:pid>")
class ProblemDetail(Resource):
    @ns.doc("get_problem")
    @ns.expect(problem_detail_get_input)
    @marshal_with(ns, problem_detail_get_output)
    def get(self, pid):
        """Gets the public details of a problem for viewing/solving."""
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
        content_map = {f: (path / "file" / f).open(encoding="utf-8").read() for f in files}
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


@ns.route("/<string:pid>/manage")
class ProblemManage(Resource):
    @ns.doc("get_manageable_problem_details")
    @marshal_with(ns, manageable_problem_details_model)
    def get(self, pid: str):
        """Gets detailed problem data for management and editing."""
        args = request_parser().parse_args()
        user = get_api_user(args)
        pid = secure_filename(pid)
        pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
        dat = pdat.new_datas
        if not user.has(objs.Permission.admin) and user.data not in dat.users:
            abort(403, "You do not have permission to manage this problem.")

        bg_action = problemsetting.check_background_action(pid)
        if bg_action is not None:
            return api_response({
                "pid": pid,
                "background_action": {"log": bg_action[0], "action_name": bg_action[1]}
            })

        p_path = preparing_problem_path / pid
        public_files = [f.name for f in (p_path / "public_file").iterdir() if f.is_file() and f.name != ".gitkeep"]
        default_checkers = [s for s in os.listdir("testlib/checkers") if s.endswith(".cpp")]
        default_interactors = [s for s in os.listdir("testlib/interactors") if s.endswith(".cpp")]
        action_path = p_path / "actions"
        actions = [f.stem for f in action_path.iterdir() if f.suffix == ".json"] if action_path.is_dir() else []
        collaborators = [u for u in dat.users]

        return api_response({
            "pid": pid,
            "name": pdat.name,
            "is_public": pdat.is_public,
            "data": objs.as_dict(dat),
            "versions": [v for v in problemsetting.query_versions(pdat)],
            "public_files": public_files,
            "default_checkers": default_checkers,
            "available_languages": list(executing.langs.keys()),
            "default_interactors": default_interactors,
            "collaborators": collaborators,
            "current_actions": actions,
        })


@ns.route("/<string:pid>/manage/preview")
class ProblemPreview(Resource):
    @ns.doc(description="Previews a problem component (e.g., statement HTML). Returns raw content.")
    @server.limiter.limit(config.server.file_limit)
    def get(self, pid: str):
        """Previews a problem component."""
        auth_args = request_parser().parse_args()
        user = get_api_user(auth_args)
        pid = secure_filename(pid)
        pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
        dat = pdat.new_datas
        if not user.has(objs.Permission.admin) and user.data not in dat.users:
            abort(403, "You do not have permission to preview this problem.")

        if (problem_path / pid / "waiting").is_file():
            return api_response({
                "status": "busy",
                "action": tools.read(pdat.path / "waiting")
            }, status_code=503)

        preview_args = request.args.to_dict()
        preview_args['pid'] = pid
        return problemsetting.preview(preview_args, pdat)
