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
from flask_restx import Resource, fields
from werkzeug.utils import secure_filename

from .base import (get_api_user, api_response, api, marshal_with, request_parser, Form, paging, pagination, Args, File,
                   base_request_parser)
from ... import objs, problemsetting, datas, executing, constants, tools, config, server, contests
from ...constants import preparing_problem_path, problem_path

ns = api.namespace("problem", path="/problem", description="Problem related API endpoints")

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
    "data": fields.List(fields.Nested(problem_list_result_item), description="List of problems"),
    "show_pages": fields.List(fields.Integer, description="List of page numbers to display in pagination")
})
problem_detail_get_output = ns.model("ProblemDetailOutput", {
    "pid": fields.String(description="Problem ID"),
    "title": fields.String(description="Title of the problem"),
    "statement": fields.String(description="Problem statement in Markdown format"),
    "statement_html": fields.String(description="Problem statement in HTML format"),
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
    "version": fields.String(description="Version hash"),
    "description": fields.String(description="Version description"),
    "create_time": fields.Float(description="Creation timestamp"),
})
manageable_problem_details_model = ns.model("ManageableProblemDetails", {
    "pid": fields.String(description="Problem ID"),
    "name": fields.String(description="Problem name"),
    "is_public": fields.Boolean(description="Whether the problem is public"),
    "data": fields.Raw(description="The full editable ProblemData object"),
    "versions": fields.List(fields.Nested(version_info_model), description="List of problem versions"),
    "public_files": fields.List(fields.String, description="List of public files"),
    "default_checkers": fields.List(fields.String, description="List of available default checkers"),
    "available_languages": fields.List(fields.String, description="List of available programming languages"),
    "default_interactors": fields.List(fields.String, description="List of available default interactors"),
    "collaborators": fields.List(fields.String, description="List of collaborators"),
    "current_actions": fields.List(fields.String, description="List of available background actions"),
    "background_action": fields.Raw(description="Current running background action, if any", required=False)
})
# endregion

# region Parsers
problem_post_input = request_parser(
    Form("name", "Title of the problem", required=True),
    Form("pid", "Target pid of the problem", required=False),
    File("zip_file", "Content of the problem in zip file", required=False)
)
problem_get_input = request_parser(
    *paging(),
    Args("manageable", "List problems the user can manage", type=str, required=False, default="false",
         choices=["true", "false"])
)
problem_detail_get_input = request_parser()


# endregion


@ns.route("")
class ProblemIndex(Resource):
    @ns.doc("create_problem")
    @ns.expect(problem_post_input)
    @marshal_with(ns, problem_post_output)
    def post(self):
        """Creates a new problem."""
        args = problem_post_input.parse_args()
        user = get_api_user(args, objs.Permission.make_problems)
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
        """Lists problems. Can list either public problems or problems the user can manage."""
        args = problem_get_input.parse_args()
        user = get_api_user(args, require_login=False)

        if args.get('manageable') == "true":
            if not user.is_authenticated:
                server.custom_abort(403, "Authentication required to list manageable problems.")

            if user.has(objs.Permission.admin):
                problem_obj = datas.Problem.query.filter(datas.Problem.pid != "test")
            elif user.has(objs.Permission.make_problems):
                problem_obj = user.data.problems.filter(datas.Problem.pid != "test")
            else:
                problem_obj = datas.Problem.query.filter_by(is_public=True)
        else:
            problem_obj = datas.Problem.query.filter_by(is_public=True)

        got_data, page_cnt, page_idx, show_pages = pagination(problem_obj, args)
        results = [{"pid": p.pid, "name": p.name} for p in got_data]
        return api_response({"page_count": page_cnt,
                             "page": page_idx,
                             "data": results,
                             "show_pages": show_pages
                             })


@ns.route("/<string:pid>")
class ProblemDetail(Resource):
    @ns.doc("get_problem")
    @ns.expect(problem_detail_get_input)
    @marshal_with(ns, problem_detail_get_output)
    def get(self, pid):
        """Gets the public details of a problem for viewing/solving."""
        args = problem_detail_get_input.parse_args()
        user = get_api_user(args, require_login=False)
        pdat: datas.Problem = datas.first(datas.Problem, pid=pid)
        if pdat is None:
            server.custom_abort(404, f"Problem {pid!r} not found.")
        dat = pdat.datas
        if not pdat.is_public and (not user.is_authenticated or
                                   (not user.has(objs.Permission.admin) and user.id not in dat.users)):
            server.custom_abort(403, "You do not have permission to view this problem.")
        langs = [lang for lang in executing.langs.keys() if pdat.lang_allowed(lang)]
        path = constants.problem_path / pid
        statement = tools.read(path / "statement.md") if (path / "statement.md").is_file() else ""
        statement_html = tools.read(path / "statement.html") if (path / "statement.html").is_file() else ""
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
            "statement_html": statement_html,
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
    @ns.expect(base_request_parser)
    @marshal_with(ns, manageable_problem_details_model)
    def get(self, pid: str):
        """Gets detailed problem data for management and editing."""
        args = base_request_parser.parse_args()
        user = get_api_user(args)
        pid = secure_filename(pid)
        pdat: datas.Problem = datas.first(datas.Problem, pid=pid)
        if pdat is None:
            server.custom_abort(404, f"Problem {pid!r} not found.")
        dat = pdat.new_datas
        if not user.has(objs.Permission.admin) and user.data not in dat.users:
            server.custom_abort(403, "You do not have permission to manage this problem.")

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


problem_preview_input = request_parser(
    Args("type", "Content Type", type=str, required=True,
         choices=["statement", "public_file", "file", "testcases", "testcases_gen"]),
    Args("name", "Content name", type=str, required=False)
)


@ns.route("/<string:pid>/manage/preview")
class ProblemPreview(Resource):
    @ns.doc(description="Previews a problem component (e.g., statement HTML). Returns raw content.")
    @ns.expect(problem_preview_input)
    @server.limiter.limit(config.server.file_limit)
    def get(self, pid: str):
        """Previews a problem component."""
        auth_args = problem_preview_input.parse_args()
        user = get_api_user(auth_args)
        pid = secure_filename(pid)
        pdat: datas.Problem = datas.first(datas.Problem, pid=pid)
        if pdat is None:
            server.custom_abort(404, f"Problem {pid!r} not found.")
        dat = pdat.new_datas
        if not user.has(objs.Permission.admin) and user.data not in dat.users:
            server.custom_abort(403, "You do not have permission to preview this problem.")

        if (problem_path / pid / "waiting").is_file():
            return api_response({
                "status": "busy",
                "action": tools.read(pdat.path / "waiting")
            }, status_code=503)

        preview_args = request.args.to_dict()
        preview_args['pid'] = pid
        return problemsetting.preview(preview_args, pdat)


problem_file_input = request_parser(
    Args("cid", "Contest ID if applicable", type=str, required=False)
)


@ns.route("/<string:pid>/file/<string:filename>")
class ProblemFile(Resource):
    @ns.doc("get_problem_file")
    @ns.expect(problem_file_input)
    def get(self, pid: str, filename: str):
        """Serve a public file associated with a problem."""
        args = problem_file_input.parse_args()
        user = get_api_user(args, require_login=False)
        idx = secure_filename(pid)
        filename = secure_filename(filename)

        if args.get("cid"):
            cdat = datas.first(datas.Contest, cid=args["cid"])
            if cdat is None:
                server.custom_abort(404, "Contest not found.")
            found_problem = False
            for obj in cdat.datas.problems.values():
                if obj.pid == idx:
                    found_problem = True
                    break
            if not found_problem:
                server.custom_abort(404, "Problem not found in contest.")
            contests.check_access(cdat, user)
        else:
            pdat = datas.first(datas.Problem, pid=idx)
            if pdat is None:
                server.custom_abort(404, "Problem not found.")
            dat = pdat.datas
            if not pdat.is_public:
                if not user.is_authenticated:
                    server.custom_abort(403, "You has no permission to access this file.")
                if not user.has(objs.Permission.admin) and user.id not in dat.users:
                    server.custom_abort(403, "You has no permission to access this file.")
        target = constants.problem_path / idx / "public_file" / filename
        if not target.is_file():
            server.custom_abort(404, "File not found.")
        return server.sending_file(target)
