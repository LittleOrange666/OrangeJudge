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
from flask_restx import Resource, abort
from werkzeug.utils import secure_filename

from .base import get_api_user, api_response, api, request_parser, Form, File
from ... import problemsetting, datas, objs, executing
from ...constants import problem_path

ns = api.namespace("problem_actions", path="/problem/<string:pid>/manage",
                   description="Detailed problem management actions")


class BaseProblemAction(Resource):
    action_name = ""
    action_input = request_parser()

    def do_post(self, pid: str):
        auth_args = self.action_input.parse_args()
        user = get_api_user(auth_args)
        pid = secure_filename(pid)
        pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
        permission_dat = pdat.new_datas
        if not user.has(objs.Permission.admin) and user.data.username not in permission_dat.users:
            abort(403, "You do not have permission to perform this action on this problem.")
        if (problem_path / pid / "waiting").is_file() or problemsetting.check_background_action(pid) is not None:
            abort(503, "A background action is already in progress.")
        action_func = problemsetting.actions.get(self.action_name)
        is_important = hasattr(action_func, "important") and getattr(action_func, "important")
        with problemsetting.Problem(pid, is_important) as dat:
            result = action_func(request.form, dat)
            if isinstance(result, str):
                return api_response({"status": "success", "view_hint": result})
            elif isinstance(result, Response):
                return result
            abort(500, f"Action handler for '{self.action_name}' returned an unexpected result.")


@ns.route("/save_general_info")
class SaveGeneralInfo(BaseProblemAction):
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
    def post(self, pid: str):
        """Save general information of the problem."""
        return self.do_post(pid)


@ns.route("/create_version")
class CreateVersion(BaseProblemAction):
    action_name = "create_version"
    action_input = request_parser(
        Form("description", "Version description", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Create a new version of the problem."""
        return self.do_post(pid)


@ns.route("/save_statement")
class SaveStatement(BaseProblemAction):
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
    def post(self, pid: str):
        """Save the problem statement."""
        return self.do_post(pid)


@ns.route("/upload_zip")
class UploadZip(BaseProblemAction):
    action_name = "upload_zip"
    action_input = request_parser(
        Form("input_ext", "Input file suffix", str, required=True),
        Form("output_ext", "Output file suffix", str, required=True),
        File("zip_file", "ZIP file containing testcases", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Upload a ZIP file containing multiple testcases."""
        return self.do_post(pid)


@ns.route("/upload_testcase")
class UploadTestcase(BaseProblemAction):
    action_name = "upload_testcase"
    action_input = request_parser(
        Form("input_name", "Input filename", str, required=True),
        Form("output_name", "Output filename", str, required=True),
        Form("input_content", "Input content", str, required=True),
        Form("output_content", "Output content", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Upload a single testcase file."""
        return self.do_post(pid)


@ns.route("/remove_testcase")
class RemoveTestcase(BaseProblemAction):
    action_name = "remove_testcase"
    action_input = request_parser(
        Form("idx", "Testcase index", int, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove a single testcase file."""
        return self.do_post(pid)


@ns.route("/remove_all_testcase")
class RemoveAllTestcase(BaseProblemAction):
    action_name = "remove_all_testcase"
    action_input = request_parser()

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove all testcase files."""
        return self.do_post(pid)


@ns.route("/upload_public_file")
class UploadPublicFile(BaseProblemAction):
    action_name = "upload_public_file"
    action_input = request_parser(
        File("files", "Public files to upload", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Upload a public file for the problem."""
        return self.do_post(pid)


@ns.route("/remove_public_file")
class RemovePublicFile(BaseProblemAction):
    action_name = "remove_public_file"
    action_input = request_parser(
        Form("filename", "Filename to remove", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove a public file from the problem."""
        return self.do_post(pid)


@ns.route("/upload_file")
class UploadFile(BaseProblemAction):
    action_name = "upload_file"
    action_input = request_parser(
        File("files", "Files to upload", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Upload a file for the problem."""
        return self.do_post(pid)


@ns.route("/create_file")
class CreateFile(BaseProblemAction):
    action_name = "create_file"
    action_input = request_parser(
        Form("filename", "Filename to create", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Create a new file for the problem."""
        return self.do_post(pid)


@ns.route("/remove_file")
class RemoveFile(BaseProblemAction):
    action_name = "remove_file"
    action_input = request_parser(
        Form("filename", "Filename to remove", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove a file from the problem."""
        return self.do_post(pid)


@ns.route("/save_file_content")
class SaveFileContent(BaseProblemAction):
    action_name = "save_file_content"
    action_input = request_parser(
        Form("filename", "Filename", str, required=True),
        Form("content", "File content", str, required=True),
        Form("type", "File type (language)", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Save the content of a file for the problem."""
        return self.do_post(pid)


@ns.route("/choose_checker")
class ChooseChecker(BaseProblemAction):
    action_name = "choose_checker"
    action_input = request_parser(
        Form("checker_type", "Checker type", str, required=True, choices=["my", "default"]),
        Form("my_checker", "My checker filename", str, required=False),
        Form("default_checker", "Default checker filename", str, required=False)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Choose a checker for the problem."""
        return self.do_post(pid)


@ns.route("/choose_interactor")
class ChooseInteractor(BaseProblemAction):
    action_name = "choose_interactor"
    action_input = request_parser(
        Form("my_interactor", "Interactor filename", str, required=False),
        Form("enable_interactor", "Enable interactor", str, required=False, choices=["on", "off"], default="off")
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Choose an interactor for the problem."""
        return self.do_post(pid)


@ns.route("/choose_codechecker")
class ChooseCodechecker(BaseProblemAction):
    action_name = "choose_codechecker"
    action_input = request_parser(
        Form("my_codechecker", "Codechecker filename", str, required=False),
        Form("codechecker_mode", "Codechecker mode", str, required=True, choices=["disabled", "public", "private"])
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Choose a code checker for the problem."""
        return self.do_post(pid)


@ns.route("/choose_runner")
class ChooseRunner(BaseProblemAction):
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
    def post(self, pid: str):
        """Choose a runner for the problem."""
        return self.do_post(pid)


@ns.route("/choose_sample")
class ChooseSample(BaseProblemAction):
    action_name = "choose_sample"
    action_input = request_parser(
        *(
            Form(f"my_sample_{k}", f"Sample code for {v.branch}", str, required=False)
            for k, v in executing.langs.items()
        )
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Choose sample code for the problem."""
        return self.do_post(pid)


@ns.route("/add_library")
class AddLibrary(BaseProblemAction):
    action_name = "add_library"
    action_input = request_parser(
        Form("library", "Library filename", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Add a library to the problem."""
        return self.do_post(pid)


@ns.route("/remove_library")
class RemoveLibrary(BaseProblemAction):
    action_name = "remove_library"
    action_input = request_parser(
        Form("name", "Library filename to remove", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove a library from the problem."""
        return self.do_post(pid)


@ns.route("/save_testcase")
class SaveTestcase(BaseProblemAction):
    action_name = "save_testcase"
    action_input = request_parser(
        Form("modify", "Modifications (JSON)", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Save testcase information for the problem."""
        return self.do_post(pid)


@ns.route("/do_generate")
class DoGenerate(BaseProblemAction):
    action_name = "do_generate"
    action_input = request_parser()

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Generate testcases for the problem."""
        return self.do_post(pid)


@ns.route("/create_group")
class CreateGroup(BaseProblemAction):
    action_name = "create_group"
    action_input = request_parser(
        Form("name", "Group name", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Create a new group for the problem."""
        return self.do_post(pid)


@ns.route("/remove_group")
class RemoveGroup(BaseProblemAction):
    action_name = "remove_group"
    action_input = request_parser(
        Form("name", "Group name to remove", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove a group from the problem."""
        return self.do_post(pid)


@ns.route("/save_groups")
class SaveGroups(BaseProblemAction):
    action_name = "save_groups"
    action_input = request_parser()

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Save group information for the problem."""
        return self.do_post(pid)


@ns.route("/protect_problem")
class ProtectProblem(BaseProblemAction):
    action_name = "protect_problem"
    action_input = request_parser()

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Protect the problem."""
        return self.do_post(pid)


@ns.route("/public_problem")
class PublicProblem(BaseProblemAction):
    action_name = "public_problem"
    action_input = request_parser()

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Make the problem public."""
        return self.do_post(pid)


@ns.route("/save_languages")
class SaveLanguages(BaseProblemAction):
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
    def post(self, pid: str):
        """Save allowed programming languages for the problem."""
        return self.do_post(pid)


@ns.route("/create_gen_group")
class CreateGenGroup(BaseProblemAction):
    action_name = "create_gen_group"
    action_input = request_parser(
        Form("file1", "Generator file", str, required=True),
        Form("file2", "Solution file", str, required=True),
        Form("group", "Group name", str, required=True),
        Form("type", "Type", str, required=True, choices=["sol", "gen"]),
        Form("mul", "Multiplier", int, required=True),
        Form("cmds", "Commands", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Create a new generation group for the problem."""
        return self.do_post(pid)


@ns.route("/update_gen_group")
class UpdateGenGroup(BaseProblemAction):
    action_name = "update_gen_group"
    action_input = request_parser(
        Form("file1", "Generator file", str, required=True),
        Form("file2", "Solution file", str, required=True),
        Form("group", "Group name", str, required=True),
        Form("type", "Type", str, required=True, choices=["sol", "gen"]),
        Form("idx", "Index", int, required=True),
        Form("cmds", "Commands", str, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Update a generation group for the problem."""
        return self.do_post(pid)


@ns.route("/remove_gen_group")
class RemoveGenGroup(BaseProblemAction):
    action_name = "remove_gen_group"
    action_input = request_parser(
        Form("idx", "Index to remove", int, required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Remove a generation group from the problem."""
        return self.do_post(pid)


@ns.route("/import_polygon")
class ImportPolygon(BaseProblemAction):
    action_name = "import_polygon"
    action_input = request_parser(
        File("zip_file", "Polygon ZIP file", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Import a problem from Polygon."""
        return self.do_post(pid)


@ns.route("/import_problem")
class ImportProblem(BaseProblemAction):
    action_name = "import_problem"
    action_input = request_parser(
        File("zip_file", "Problem ZIP file", required=True)
    )

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Import a problem from another source."""
        return self.do_post(pid)


@ns.route("/export_problem")
class ExportProblem(BaseProblemAction):
    action_name = "export_problem"
    action_input = request_parser()

    @ns.doc("problem_" + action_name)
    @ns.expect(action_input)
    def post(self, pid: str):
        """Export the problem to a specified format."""
        return self.do_post(pid)
