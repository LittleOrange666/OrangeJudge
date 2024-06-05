import traceback

from flask import Flask, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session
from flask_wtf import CSRFProtect

from modules import tools

app = Flask(__name__, static_url_path='/static', static_folder="../static/", template_folder="../templates/")
app.config['SECRET_KEY'] = 'HP4xkCix2nf5qCmxSXV0sBwocE2CjECC5z2T9TKQmv8'
app.config['SESSION_TYPE'] = "filesystem"
app.config["SESSION_FILE_DIR"] = "sessions"
# app.config['SESSION_USE_SIGNER'] = True
# app.config['SECRET_KEY'] = os.urandom(24)
app.config["SESSION_COOKIE_NAME"] = "OrangeJudgeSession"
app.config['SESSION_PERMANENT'] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 3000000
Session(app)
CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20/minute"],
    storage_uri="redis://localhost:6379",
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window"
)


@app.errorhandler(400)
def error_400(error):
    if request.method == "GET":
        return render_template("400.html"), 400
    else:
        return "400 Bad Request", 400


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


@app.errorhandler(Exception)
def error_500(error: Exception):
    target = tools.random_string()
    with open(f"logs/{target}.log", "w", encoding="utf-8") as f:
        traceback.print_exception(error, file=f)
    if request.method == "POST":
        return target, 500
    return render_template("500.html", log_uid=target), 500