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
from dataclasses import dataclass
from functools import wraps
from typing import Any

from flask import Blueprint, request
from flask_login import current_user
from flask_restx import Api, fields, Namespace, reqparse
from flask_restx.reqparse import ParseResult
from flask_wtf.csrf import validate_csrf
from loguru import logger
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequestKeyError, HTTPException

from ... import server, login, objs, tools, constants
from ...constants import log_path

app = server.app

blueprint = Blueprint("api", __name__, url_prefix="/api")
server.csrf_exempt(blueprint)

api = Api(blueprint, title="OrangeJudge API", description="API for OrangeJudge, a competitive programming platform",
          doc="/api-docs")


@api.errorhandler(BadRequestKeyError)
def handle_missing_param(e):
    missing_key = e.args[0] if e.args else "unknown"
    msg = "missing parameter" if request.method == "GET" else "missing form parameter"
    return {
        "status": "error",
        "description": msg,
        "missing": missing_key,
        "error_code": 400
    }, 400


@api.errorhandler(server.CustomHTTPException)
def custom_http_exception(error: server.CustomHTTPException):
    return {"status": "error",
            "error_code": error.code,
            "description": error.description
            }, error.code


@api.errorhandler(HTTPException)
def api_http_exception(error: HTTPException):
    return {"status": "error",
            "error_code": error.code,
            "description": error.description
            }, error.code


@api.errorhandler(Exception)
def error_500(error: Exception):
    target = tools.random_string()
    log_file = (log_path / f"{target}.log")
    with log_file.open("w") as f:
        traceback.print_exception(error, file=f)
    log_content = log_file.read_text()
    logger.warning(f"Error: {log_content}")
    return {"status": "error",
            "error_code": 500,
            "description": "500 Internal Server Error",
            "log_uid": target
            }, 500


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


def get_api_user(args: ParseResult, required: objs.Permission | None = None) -> login.User:
    username = args["username"]
    user = login.User(username)
    if not user.valid():
        server.custom_abort(404, "User not found")
    if current_user.is_authenticated and current_user.id == username and verify_csrf():
        return current_user
    key = args.get("api-key")
    if not key and request.headers.get("api-key"):
        key = request.headers.get("api-key")
    if not key:
        server.custom_abort(403, "Missing API key")
    if not user.check_api_key(key):
        server.custom_abort(403, "API key not match")
    if required is not None and not user.has(required):
        server.custom_abort(403, f"Required '{required.name}' permission")
    return user


def api_response(data: dict, status_code: int = 200) -> tuple[dict, int]:
    """
    Create a standardized JSON response.

    Args:
        data (dict): The data to include in the response.
        status_code (int): The HTTP status code for the response. Defaults to 200.

    Returns:
        tuple[dict, int]: A tuple containing the response data and the status code.
    """
    return {"status": "success", "data": data}, status_code


def marshal_with(ns: Namespace, success_model):
    def error_model(code, description):
        return code, description, ns.model("ErrorResponse"+str(code), {
            "status": fields.String(required=True, example="error"),
            "error_code": fields.Integer(required=True, example=code),
            "description": fields.String(required=True, example=description),
        })

    true_success_model = ns.model("Full" + success_model.name, {
        "status": fields.String(required=True, example="success"),
        "data": fields.Nested(success_model)
    })

    def decorator(func):
        f = ns.response(*error_model(400, "Bad Request"))(func)
        f = ns.response(*error_model(403, "Forbidden"))(f)
        f = ns.response(*error_model(404, "Not Found"))(f)
        f = ns.response(*error_model(409, "Conflict"))(f)
        f = ns.response(*error_model(500, "Internal Server Error"))(f)
        f = ns.response(*error_model(503, "Service Unavailable"))(f)
        f = ns.marshal_with(true_success_model, code=200, description="Success")(f)

        @wraps(func)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        return wrapper

    return decorator


class MyField:
    def __init__(self):
        self.name = None

    def to_kwargs(self) -> dict[str, Any]:
        return {}


@dataclass
class Form(MyField):
    name: str
    help: str | None = None
    type: type = str
    required: bool = True
    default: Any = None

    def to_kwargs(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "required": self.required,
            "help": self.help,
            "location": "form",
            "default": self.default
        }


@dataclass
class Args(MyField):
    name: str
    help: str | None = None
    type: type = str
    required: bool = True
    default: Any = None

    def to_kwargs(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "required": self.required,
            "help": self.help,
            "location": "args",
            "default": self.default
        }


@dataclass
class File(MyField):
    name: str
    help: str | None = None
    type: type = FileStorage
    required: bool = True

    def to_kwargs(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "required": self.required,
            "help": self.help,
            "location": "files"
        }


def paging() -> list[MyField]:
    return [
        Args("page", "Page number to retrieve", int, default=1),
        Args("page_size", "Number of items per page", int, default=constants.page_size)
    ]


def request_parser(*args: MyField) -> reqparse.RequestParser:
    parser = reqparse.RequestParser()
    parser.add_argument("username", type=str, required=True, help="Username of the user using the api",
                        location="values")
    parser.add_argument("api-key", type=str, required=False, help="Api key to authenticate the user",
                        location=("form", "headers"))
    for arg in args:
        kwargs = arg.to_kwargs()
        parser.add_argument(arg.name, **kwargs)
    return parser


def pagination(sql_obj, args: ParseResult, rev: bool = True) -> tuple[list, int, int, list[int]]:
    page = args["page"]
    page_size = args["page_size"]
    return tools.pagination(sql_obj, rev, page, page_size)
