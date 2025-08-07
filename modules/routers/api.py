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

from flask import Blueprint, request, abort

from .. import server, login, objs, submitting

app = server.app

blueprint = Blueprint("api", __name__, url_prefix="/api")
server.csrf_exempt(blueprint)


def get_api_user(username: str, required: objs.Permission | None = None) -> login.User:
    if request.method == "GET":
        if "key" not in request.args:
            abort(403)
        key = request.args.get("key")
    elif request.method == "POST":
        if "key" not in request.form:
            abort(403)
        key = request.form.get("key")
    else:
        abort(405)
    user = login.User(username)
    if not user.check_api_key(key):
        abort(403)
    if required is not None and not user.has(required):
        abort(403)
    return user


@blueprint.route("/submit", methods=["POST"])
def submit():
    user = get_api_user(request.form["username"])
    lang = request.form["lang"]
    code = request.form["code"].replace("\n\n", "\n")
    pid = request.form["pid"]
    cid = request.form.get("cid")
    if pid == "test":
        inp = request.form["input"]
        idx = submitting.test_submit(lang, code, inp, user)
    else:
        idx = submitting.submit(lang, pid, code, cid, user)
    return {"status": "success", "submission_id": idx}, 200


app.register_blueprint(blueprint)  # this is needed to be at the end of the file
