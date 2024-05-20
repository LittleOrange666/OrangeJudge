import os
from flask_sqlalchemy import SQLAlchemy

from modules import server

datafile = os.path.abspath(os.path.join(os.getcwd(), "data", "data.sqlite"))
app = server.app
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + datafile
db = SQLAlchemy(app)
