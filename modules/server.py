import traceback

from flask import Flask, render_template, request, session
from flask_session import Session
from flask_wtf import CSRFProtect

from modules import tools

app = Flask(__name__, static_url_path='/static', static_folder="../static/", template_folder="../templates/")
app.secret_key = 'HP4xkCix2nf5qCmxSXV0sBwocE2CjECC5z2T9TKQmv8'
app.config['SESSION_TYPE'] = "filesystem"
app.config["SESSION_FILE_DIR"] = "sessions"
app.config["SESSION_COOKIE_NAME"] = "OrangeJudgeSession"
app.config["PERMANENT_SESSION_LIFETIME"] = 3000000
Session(app)
CSRFProtect(app)


@app.before_request
def make_session_permanent():
    session.permanent = True


@app.errorhandler(400)
def error_400(error):
    return render_template("400.html"), 400


@app.errorhandler(403)
def error_403(error):
    return render_template("403.html"), 403


@app.errorhandler(404)
def error_404(error):
    return render_template("404.html"), 404


@app.errorhandler(409)
def error_409(error):
    return render_template("404.html"), 409


@app.errorhandler(Exception)
def error_500(error: Exception):
    target = tools.random_string()
    with open(f"logs/{target}.log", "w", encoding="utf-8") as f:
        traceback.print_exception(error, file=f)
    if request.method == "POST":
        return target, 500
    return render_template("500.html", log_uid=target), 500
