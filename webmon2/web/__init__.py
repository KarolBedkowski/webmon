""" Web interface """

from flask import g

from webmon2.database import DB

from .app import start_app

__all__ = (
    "start_app",
    "get_db",
)


def get_db():
    database = getattr(g, "_database", None)
    if database is None:
        database = g._database = DB.get()
    return database
