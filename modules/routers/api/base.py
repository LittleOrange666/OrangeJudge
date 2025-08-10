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
import traceback

from flask import Blueprint, request, abort, jsonify, Response
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from werkzeug.exceptions import BadRequestKeyError
from loguru import logger

from ...constants import log_path
from ... import server, login, objs, tools

app = server.app

blueprint = Blueprint("api", __name__, url_prefix="/api")
server.csrf_exempt(blueprint)


@blueprint.errorhandler(BadRequestKeyError)
def handle_missing_param(e):
    missing_key = e.args[0] if e.args else "unknown"
    msg = "missing parameter" if request.method == "GET" else "missing form parameter"
    return jsonify({
        "status": "error",
        "description": msg,
        "missing": missing_key,
        "error_code": 400
    }), 400


@blueprint.errorhandler(server.CustomHTTPException)
def custom_http_exception(error: server.CustomHTTPException):
    return jsonify({"status": "error",
                    "error_code": error.code,
                    "description": error.description}
                   ), error.code


@blueprint.errorhandler(403)
def error_403(error):
    return jsonify({"status": "error",
                    "error_code": 403,
                    "description": "403 Forbidden"
                    }), 403


@blueprint.errorhandler(404)
def error_404(error):
    return jsonify({"status": "error",
                    "error_code": 404,
                    "description": "404 Not Found"
                    }), 404


@blueprint.errorhandler(405)
def error_405(error):
    return jsonify({"status": "error",
                    "error_code": 405,
                    "description": "405 Method Not Allowed"
                    }), 405


@blueprint.errorhandler(409)
def error_409(error):
    return jsonify({"status": "error",
                    "error_code": 409,
                    "description": "409 Conflict"
                    }), 409


@blueprint.errorhandler(429)
def error_429(error):
    return jsonify({"status": "error",
                    "error_code": 429,
                    "description": "429 Too Many Request"
                    }), 429


@blueprint.errorhandler(503)
def error_503(error):
    return jsonify({"status": "error",
                    "error_code": 503,
                    "description": "503 Service Unavailable"
                    }), 503


@blueprint.errorhandler(Exception)
def error_500(error: Exception):
    target = tools.random_string()
    log_file = (log_path / f"{target}.log")
    with log_file.open("w") as f:
        traceback.print_exception(error, file=f)
    log_content = log_file.read_text()
    logger.warning(f"Error: {log_content}")
    return jsonify({"status": "error",
                    "error_code": 500,
                    "description": "500 Internal Server Error",
                    "log_uid": target
                    }), 500


def verify_csrf() -> bool:
    """
    Verify the validity of the CSRF (Cross-Site Request Forgery) token.

    This function checks the server configuration and request context to determine
    if CSRF validation should be performed. If CSRF validation is disabled or the
    request method is GET, it returns True. Otherwise, it attempts to extract the
    CSRF token from the request form or headers and validates it using Flask-WTF's
    `validate_csrf` function.

    Returns:
        bool: True if CSRF validation passes, False otherwise.
    """
    if server.config.debug.disable_csrf:
        return True
    if request.method == "GET":
        return True
    if "csrf_token" not in request.form:
        if request.headers.get("x-csrf-token"):
            csrf_token = request.headers.get("x-csrf-token")
        else:
            return False
    else:
        csrf_token = request.form.get("csrf_token")
    if not validate_csrf(csrf_token):
        return False
    return True


def get_api_user(username: str, required: objs.Permission | None = None) -> login.User:
    """
    Retrieve the API user based on the provided username and optional permission requirements.

    This function checks if the current user is authenticated and matches the provided username.
    If not, it verifies the API key from the request arguments or form data. It also ensures
    that the user has the required permissions if specified.

    Args:
        username (str): The username of the API user to retrieve.
        required (objs.Permission | None, optional): The permission required for the user. Defaults to None.

    Returns:
        login.User: The API user object corresponding to the provided username.

    Raises:
        403: If the API key is missing, invalid, or the user lacks the required permissions.
        405: If the request method is not GET or POST.
    """
    user = login.User(username)
    if not user.valid():
        server.custom_abort(404, "User not found")
    if current_user.is_authenticated and current_user.username == username and verify_csrf():
        return current_user
    if "x-api-key" in request.headers:
        key = request.headers.get("x-api-key")
    elif request.method == "GET":
        if "key" not in request.args:
            server.custom_abort(403, "Missing API key")
        key = request.args.get("key")
    else:
        if "key" not in request.form:
            server.custom_abort(403, "Missing API key")
        key = request.form.get("key")
    if not user.check_api_key(key):
        server.custom_abort(403, "API key not match")
    if required is not None and not user.has(required):
        server.custom_abort(403, f"Required '{required.name}' permission")
    return user


def api_response(data: dict, status_code: int = 200) -> tuple[Response, int]:
    """
    Create a standardized JSON response.

    Args:
        data (dict): The data to include in the response.
        status_code (int): The HTTP status code for the response. Defaults to 200.

    Returns:
        tuple[dict, int]: A tuple containing the response data and the status code.
    """
    return jsonify(status="success", data=data), status_code
