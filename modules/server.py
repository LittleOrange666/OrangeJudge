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
import secrets
import socket
import traceback
from pathlib import Path

import redis
from flask import Flask, render_template, request, Response, abort, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user
from flask_session import Session
from flask_wtf import CSRFProtect
from loguru import logger

from . import tools, config, objs
from .constants import log_path

app = Flask(__name__, static_url_path='/static', static_folder="../static/", template_folder="../templates/")
if config.debug.single_secret:
    app.config['SECRET_KEY'] = '2lGU53x5P7HujHeoqk5X-IDrK1sSj4RQBeGU84CMpkGJ'
elif "FLASK_SECRET_KEY" in os.environ:
    app.config['SECRET_KEY'] = os.environ["FLASK_SECRET_KEY"]
else:
    app.config['SECRET_KEY'] = secrets.token_urlsafe(33)
redis_host = os.environ.get("REDIS_HOST", "localhost")
app.config['SESSION_TYPE'] = "redis"
app.config["SESSION_COOKIE_NAME"] = "OrangeJudgeSession"
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis.StrictRedis(host=redis_host)
app.config['SESSION_KEY_PREFIX'] = 'session:'
app.config['SESSION_PERMANENT'] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 200000
Session(app)
csrf: CSRFProtect | None = None
if not config.debug.disable_csrf:
    csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=config.server.limits,
    storage_uri=f"redis://{redis_host}:6379",
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",
    key_prefix="limiter:"
)
if config.server.admin_fast:
    @limiter.request_filter
    def admin_fast():
        return current_user.is_authenticated and current_user.has(objs.Permission.admin)


@app.errorhandler(400)
def error_400(error):
    if request.method == "GET":
        return render_template("400.html"), 400
    else:
        return error.description, 400


@app.errorhandler(403)
def error_403(error):
    if request.method == "GET":
        return render_template("403.html"), 403
    else:
        return "403 Forbidden", 403


@app.errorhandler(404)
def error_404(error):
    if request.method == "GET":
        return render_template("404.html"), 404
    else:
        return "404 Not Found", 404


@app.errorhandler(405)
def error_405(error):
    return "405 Method not Allowed", 405


@app.errorhandler(409)
def error_409(error):
    if request.method == "GET":
        return render_template("409.html"), 409
    else:
        return "409 Conflict", 409


@app.errorhandler(429)
def error_429(error):
    if request.method == "GET":
        return render_template("429.html"), 429
    else:
        return "429 Too Many Request", 429


@app.errorhandler(503)
def error_503(error):
    if request.method == "GET":
        return render_template("503.html"), 503
    else:
        return "503 Service Unavailable", 503


@app.errorhandler(Exception)
def error_500(error: Exception):
    target = tools.random_string()
    log_file = (log_path / f"{target}.log")
    with log_file.open("w") as f:
        traceback.print_exception(error, file=f)
    log_content = log_file.read_text()
    logger.warning(f"Error: {log_content}")
    if request.method == "POST":
        return target, 500
    return render_template("500.html", log_uid=target), 500


def check_port(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        result = sock.connect_ex((ip, port))
        if result == 0:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        sock.close()


def sending_file(file: Path) -> Response:
    if not file.is_file():
        abort(404)
    return send_file(file.absolute())


def csrf_exempt(f):
    if csrf is None:
        return f
    else:
        return csrf.exempt(f)
