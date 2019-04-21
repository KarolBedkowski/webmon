
from flask import current_app, g

from webmon.db import DB

from .app import start_app


def get_db():
    database = getattr(g, '_database', None)
    if database is None:
        database = g._database = DB(current_app.config['DBFILE'])
    return database
