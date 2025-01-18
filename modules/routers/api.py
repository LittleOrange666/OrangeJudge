from flask import Blueprint

from .. import server

app = server.app

blueprint = Blueprint("api", __name__, url_prefix="/api")
server.csrf_exempt(blueprint)

app.register_blueprint(blueprint)
