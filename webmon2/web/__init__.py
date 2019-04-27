""" Web interface """

from functools import wraps
from flask import g, request, redirect, url_for, session

from webmon2.database import DB

from .app import start_app

__all__ = (
    "start_app",
    "get_db",
    "login_required"
)


def get_db():
    database = getattr(g, '_database', None)
    if database is None:
        database = g._database = DB.get()
    return database


def login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if session.get('user') is None:
            return redirect(url_for('sec.login', back=request.url))
        return func(*args, **kwargs)
    return decorated_function
