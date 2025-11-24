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

from flask import request, Response
from flask_restx import Resource
from werkzeug.utils import secure_filename

from .base import get_api_user, api_response, api, request_parser, Form, File, base_request_parser
from ... import problemsetting, datas, objs, executing, server
from ...constants import problem_path

ns = api.namespace("problem_manage", path="/problem/<string:pid>/manage",
                   description="Problem management API endpoints")


def do_action(pid: str, action_name: str, action_input):
    auth_args = action_input.parse_args()
    user = get_api_user(auth_args)
    pid = secure_filename(pid)
    pdat: datas.Problem = datas.first(datas.Problem, pid=pid)
    if pdat is None:
        server.custom_abort(404, "Problem not found.")
    permission_dat = pdat.new_datas
    if not user.has(objs.Permission.admin) and user.data.username not in permission_dat.users:
        server.custom_abort(403, "You do not have permission to perform this action on this problem.")
    if (problem_path / pid / "waiting").is_file() or problemsetting.check_background_action(pid) is not None:
        server.custom_abort(503, "A background action is already in progress.")
    action_func = problemsetting.actions.get(action_name)
    is_important = hasattr(action_func, "important") and getattr(action_func, "important")
    with problemsetting.Problem(pid, is_important) as dat:
        result = action_func(request.form, dat)
        if isinstance(result, str):
            return api_response({"status": "success", "view_hint": result})
        elif isinstance(result, Response):
            return result
        server.custom_abort(500, f"Action handler for '{action_name}' returned an unexpected result.")


@ns.route("/general")
class SaveGeneralInfo(Resource):
    action_name = "save_general_info"
    action_input = request_parser(
        Form("title", "Problem title", str, required=True),
        Form("ac_info", "AC info", str, required=True),
        Form("memorylimit", "Memory limit (MB)", str, required=True),
        Form("timelimit", "Time limit (ms)", str, required=True),
        Form("show_testcase", "Show testcase", str, required=True, choices=["yes", "no"]),
        Form("show_checker", "Show checker", str, required=True, choices=["yes", "no"])
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Save general information of the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/version")
class CreateVersion(Resource):
    action_name = "create_version"
    action_input = request_parser(
        Form("description", "Version description", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Create a new version of the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/statement")
class SaveStatement(Resource):
    action_name = "save_statement"
    action_input = request_parser(
        Form("samples", "Samples (JSON)", str, required=True),
        Form("statement_full", "Full statement (Markdown)", str, required=False),
        Form("statement_main", "Main statement", str, required=False),
        Form("statement_input", "Input statement", str, required=False),
        Form("statement_output", "Output statement", str, required=False),
        Form("statement_interaction", "Interaction statement", str, required=False),
        Form("statement_scoring", "Scoring statement", str, required=False),
        Form("statement_note", "Note statement", str, required=False),
        Form("statement_type", "Statement type", str, required=False, choices=["md", "latex"])
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Save the problem statement."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/testcase")
class Testcase(Resource):
    post_action_name = "upload_testcase"
    post_action_input = request_parser(
        Form("input_name", "Input filename", str, required=True),
        Form("output_name", "Output filename", str, required=True),
        Form("input_content", "Input content", str, required=True),
        Form("output_content", "Output content", str, required=True)
    )
    delete_action_name = "remove_testcase"
    delete_action_input = request_parser(
        Form("idx", "Testcase index", int, required=True)
    )

    @ns.doc("problem_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Upload a single testcase file."""
        return do_action(pid, self.post_action_name, self.post_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, pid: str):
        """Remove a single testcase file."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)


@ns.route("/testcases")
class MultipleTestcase(Resource):
    post_action_name = "upload_zip"
    post_action_input = request_parser(
        Form("input_ext", "Input file suffix", str, required=True),
        Form("output_ext", "Output file suffix", str, required=True),
        File("zip_file", "ZIP file containing testcases", required=True)
    )
    delete_action_name = "remove_all_testcase"
    delete_action_input = base_request_parser
    put_action_name = "save_testcase"
    put_action_input = request_parser(
        Form("modify", "Modifications (JSON)", str, required=True)
    )

    @ns.doc("problem_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Upload a ZIP file containing multiple testcases."""
        return do_action(pid, self.post_action_name, self.post_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, pid: str):
        """Remove all testcase files."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)

    @ns.doc("problem_" + put_action_name)
    @ns.expect(put_action_input)
    def put(self, pid: str):
        """Save testcase information for the problem."""
        return do_action(pid, self.put_action_name, self.put_action_input)


@ns.route("/file/public")
class PublicFile(Resource):
    post_action_name = "upload_public_file"
    post_action_input = request_parser(
        File("files", "Public files to upload", required=True)
    )
    delete_action_name = "remove_public_file"
    delete_action_input = request_parser(
        Form("filename", "Filename to remove", str, required=True)
    )

    @ns.doc("problem_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Upload a public file for the problem."""
        return do_action(pid, self.post_action_name, self.post_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, pid: str):
        """Remove a public file from the problem."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)


@ns.route("/file/private")
class PrivateFile(Resource):
    post_action_name1 = "upload_file"
    post_action_name2 = "create_file"
    post_action_input = request_parser(
        File("files", "Files to upload", required=False),
        Form("filename", "Filename to create", str, required=False)
    )
    delete_action_name = "remove_file"
    delete_action_input = request_parser(
        Form("filename", "Filename to remove", str, required=True)
    )
    put_action_name = "save_file_content"
    put_action_input = request_parser(
        Form("filename", "Filename", str, required=True),
        Form("content", "File content", str, required=True),
        Form("type", "File type (language)", str, required=True)
    )

    @ns.doc("problem_" + post_action_name2, description="Upload a file or create a new file for the problem.")
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Upload or create a file for the problem."""
        res = self.post_action_input.parse_args()
        if not res.get("files") and not res.get("filename"):
            server.custom_abort(400, "Either 'files' or 'filename' must be provided.")
        if res.get("files") and res.get("filename"):
            server.custom_abort(400, "Only one of 'files' or 'filename' should be provided.")
        action_name = self.post_action_name1 if res.get("files") else self.post_action_name2
        return do_action(pid, action_name, self.post_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, pid: str):
        """Remove a file from the problem."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)

    @ns.doc("problem_" + put_action_name)
    @ns.expect(put_action_input)
    def put(self, pid: str):
        """Save the content of a file for the problem."""
        return do_action(pid, self.put_action_name, self.put_action_input)


@ns.route("/checker")
class ChooseChecker(Resource):
    action_name = "choose_checker"
    action_input = request_parser(
        Form("checker_type", "Checker type", str, required=True, choices=["my", "default"]),
        Form("my_checker", "My checker filename", str, required=False),
        Form("default_checker", "Default checker filename", str, required=False)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Choose a checker for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/interactor")
class ChooseInteractor(Resource):
    action_name = "choose_interactor"
    action_input = request_parser(
        Form("my_interactor", "Interactor filename", str, required=False),
        Form("enable_interactor", "Enable interactor", str, required=False, choices=["on", "off"], default="off")
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Choose an interactor for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/codechecker")
class ChooseCodechecker(Resource):
    action_name = "choose_codechecker"
    action_input = request_parser(
        Form("my_codechecker", "Codechecker filename", str, required=False),
        Form("codechecker_mode", "Codechecker mode", str, required=True, choices=["disabled", "public", "private"])
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Choose a code checker for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/runner")
class ChooseRunner(Resource):
    action_name = "choose_runner"
    action_input = request_parser(
        Form("enable_runner", "Enable runner", str, required=False, choices=["on", "off"], default="off"),
        *(
            Form(f"my_runner_{k}", f"Runner for {v.branch}", str, required=False)
            for k, v in executing.langs.items()
        )
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Choose a runner for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/sample")
class ChooseSample(Resource):
    action_name = "choose_sample"
    action_input = request_parser(
        *(
            Form(f"my_sample_{k}", f"Sample code for {v.branch}", str, required=False)
            for k, v in executing.langs.items()
        )
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Choose sample code for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/library")
class Library(Resource):
    post_action_name = "add_library"
    post_action_input = request_parser(
        Form("library", "Library filename", str, required=True)
    )
    delete_action_name = "remove_library"
    delete_action_input = request_parser(
        Form("name", "Library filename to remove", str, required=True)
    )

    @ns.doc("problem_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Add a library to the problem."""
        return do_action(pid, self.post_action_name, self.post_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def delete(self, pid: str):
        """Remove a library from the problem."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)


@ns.route("/generate")
class DoGenerate(Resource):
    action_name = "do_generate"
    action_input = base_request_parser

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Generate testcases for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/group")
class Group(Resource):
    post_action_name = "create_group"
    post_action_input = request_parser(
        Form("name", "Group name", str, required=True)
    )
    delete_action_name = "remove_group"
    delete_action_input = request_parser(
        Form("name", "Group name to remove", str, required=True)
    )
    put_action_name = "save_groups"
    put_action_input = request_parser()

    @ns.doc("problem_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Create a new group for the problem."""
        return do_action(pid, self.post_action_name, self.post_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def post(self, pid: str):
        """Remove a group from the problem."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)

    @ns.doc("problem_" + put_action_name)
    @ns.expect(put_action_input)
    def post(self, pid: str):
        """Save group information for the problem."""
        return do_action(pid, self.put_action_name, self.put_action_input)


@ns.route("/public")
class PublicProblem(Resource):
    action_name1 = "public_problem"
    action_name2 = "protect_problem"
    action_input = request_parser(
        Form("public", "Whether the problem is public", str, required=True, choices=["on", "off"])
    )

    @ns.doc("problem_" + action_name1)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Make the problem public."""
        res = self.action_input.parse_args()
        action_name = self.action_name1 if res.get("public") == "on" else self.action_name2
        return do_action(pid, action_name, self.action_input)


@ns.route("/language")
class SaveLanguages(Resource):
    action_name = "save_languages"
    action_input = request_parser(
        *(
            Form(f"lang_check_{k}", f"Whether {v.branch} is allowed in this problem", str, required=False, default="on",
                 choices=["on", "off"])
            for k, v in executing.langs.items()
        ),
        *(
            Form(f"lang_mul_{k}", f"Time limit multiplier of {v.branch}", int, required=False, default=1)
            for k, v in executing.langs.items()
        )
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Save allowed programming languages for the problem."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/generate/group")
class GenGroup(Resource):
    post_action_name = "create_gen_group"
    post_action_input = request_parser(
        Form("file1", "Generator file", str, required=True),
        Form("file2", "Solution file", str, required=True),
        Form("group", "Group name", str, required=True),
        Form("type", "Type", str, required=True, choices=["sol", "gen"]),
        Form("mul", "Multiplier", int, required=True),
        Form("cmds", "Commands", str, required=True)
    )
    put_action_name = "update_gen_group"
    put_action_input = request_parser(
        Form("file1", "Generator file", str, required=True),
        Form("file2", "Solution file", str, required=True),
        Form("group", "Group name", str, required=True),
        Form("type", "Type", str, required=True, choices=["sol", "gen"]),
        Form("idx", "Index", int, required=True),
        Form("cmds", "Commands", str, required=True)
    )
    delete_action_name = "remove_gen_group"
    delete_action_input = request_parser(
        Form("idx", "Index to remove", int, required=True)
    )

    @ns.doc("problem_" + post_action_name)
    @ns.expect(post_action_input)
    def post(self, pid: str):
        """Create a new generation group for the problem."""
        return do_action(pid, self.post_action_name, self.post_action_input)

    @ns.doc("problem_" + put_action_name)
    @ns.expect(put_action_input)
    def put(self, pid: str):
        """Update a generation group for the problem."""
        return do_action(pid, self.put_action_name, self.put_action_input)

    @ns.doc("problem_" + delete_action_name)
    @ns.expect(delete_action_input)
    def post(self, pid: str):
        """Remove a generation group from the problem."""
        return do_action(pid, self.delete_action_name, self.delete_action_input)


@ns.route("/import/polygon")
class ImportPolygon(Resource):
    action_name = "import_polygon"
    action_input = request_parser(
        File("zip_file", "Polygon ZIP file", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Import a problem from Polygon."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/import/standard")
class ImportProblem(Resource):
    action_name = "import_problem"
    action_input = request_parser(
        File("zip_file", "Problem ZIP file", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def put(self, pid: str):
        """Import a problem from another source."""
        return do_action(pid, self.action_name, self.action_input)


@ns.route("/export/standard")
class ExportProblem(Resource):
    action_name = "export_problem"
    action_input = base_request_parser

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def get(self, pid: str):
        """Export the problem to a specified format."""
        return do_action(pid, self.action_name, self.action_input)
