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

from .base import get_api_user, api_response, api, request_parser
from ... import problemsetting, datas, objs
from ...constants import problem_path

ns = api.namespace("problem_actions", path="/problem/<string:pid>/manage/actions",
                   description="Detailed problem management actions")


class BaseProblemAction(Resource):
    action_name = ""

    def post(self, pid: str):
        auth_args = request_parser().parse_args()
        user = get_api_user(auth_args)
        pid = secure_filename(pid)
        pdat: datas.Problem = datas.first_or_404(datas.Problem, pid=pid)
        permission_dat = pdat.new_datas
        if not user.has(objs.Permission.admin) and user.data not in permission_dat.users:
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


@ns.route("/create_version")
class CreateVersion(BaseProblemAction):
    action_name = "create_version"


@ns.route("/save_statement")
class SaveStatement(BaseProblemAction):
    action_name = "save_statement"


@ns.route("/upload_zip")
class UploadZip(BaseProblemAction):
    action_name = "upload_zip"


@ns.route("/upload_testcase")
class UploadTestcase(BaseProblemAction):
    action_name = "upload_testcase"


@ns.route("/remove_testcase")
class RemoveTestcase(BaseProblemAction):
    action_name = "remove_testcase"


@ns.route("/remove_all_testcase")
class RemoveAllTestcase(BaseProblemAction):
    action_name = "remove_all_testcase"


@ns.route("/upload_public_file")
class UploadPublicFile(BaseProblemAction):
    action_name = "upload_public_file"


@ns.route("/remove_public_file")
class RemovePublicFile(BaseProblemAction):
    action_name = "remove_public_file"


@ns.route("/upload_file")
class UploadFile(BaseProblemAction):
    action_name = "upload_file"


@ns.route("/create_file")
class CreateFile(BaseProblemAction):
    action_name = "create_file"


@ns.route("/remove_file")
class RemoveFile(BaseProblemAction):
    action_name = "remove_file"


@ns.route("/save_file_content")
class SaveFileContent(BaseProblemAction):
    action_name = "save_file_content"


@ns.route("/choose_checker")
class ChooseChecker(BaseProblemAction):
    action_name = "choose_checker"


@ns.route("/choose_interactor")
class ChooseInteractor(BaseProblemAction):
    action_name = "choose_interactor"


@ns.route("/choose_codechecker")
class ChooseCodechecker(BaseProblemAction):
    action_name = "choose_codechecker"


@ns.route("/choose_runner")
class ChooseRunner(BaseProblemAction):
    action_name = "choose_runner"


@ns.route("/choose_sample")
class ChooseSample(BaseProblemAction):
    action_name = "choose_sample"


@ns.route("/add_library")
class AddLibrary(BaseProblemAction):
    action_name = "add_library"


@ns.route("/remove_library")
class RemoveLibrary(BaseProblemAction):
    action_name = "remove_library"


@ns.route("/save_testcase")
class SaveTestcase(BaseProblemAction):
    action_name = "save_testcase"


@ns.route("/do_generate")
class DoGenerate(BaseProblemAction):
    action_name = "do_generate"


@ns.route("/create_group")
class CreateGroup(BaseProblemAction):
    action_name = "create_group"


@ns.route("/remove_group")
class RemoveGroup(BaseProblemAction):
    action_name = "remove_group"


@ns.route("/save_groups")
class SaveGroups(BaseProblemAction):
    action_name = "save_groups"


@ns.route("/protect_problem")
class ProtectProblem(BaseProblemAction):
    action_name = "protect_problem"


@ns.route("/public_problem")
class PublicProblem(BaseProblemAction):
    action_name = "public_problem"


@ns.route("/save_languages")
class SaveLanguages(BaseProblemAction):
    action_name = "save_languages"


@ns.route("/create_gen_group")
class CreateGenGroup(BaseProblemAction):
    action_name = "create_gen_group"


@ns.route("/update_gen_group")
class UpdateGenGroup(BaseProblemAction):
    action_name = "update_gen_group"


@ns.route("/remove_gen_group")
class RemoveGenGroup(BaseProblemAction):
    action_name = "remove_gen_group"


@ns.route("/import_polygon")
class ImportPolygon(BaseProblemAction):
    action_name = "import_polygon"


@ns.route("/import_problem")
class ImportProblem(BaseProblemAction):
    action_name = "import_problem"


@ns.route("/export_problem")
class ExportProblem(BaseProblemAction):
    action_name = "export_problem"
