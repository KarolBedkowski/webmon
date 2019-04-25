
from functools import wraps
from flask import current_app, g, request, redirect, url_for, session

from webmon.db import DB

from .app import start_app


def get_db():
    database = getattr(g, '_database', None)
    if database is None:
        database = g._database = DB.get()
    return database


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user') is None:
            return redirect(url_for('sec.login', back=request.url))
        return f(*args, **kwargs)
    return decorated_function
