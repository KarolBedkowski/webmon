#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""

"""

import os
import datetime

from flask import Flask, g
from gevent.pywsgi import WSGIServer
from docutils.core import publish_parts


def _docutils_filter(body):
    if not body:
        return body
    return publish_parts(
        body, writer_name='html', settings=None)['fragment']


def _age_filter(date):
    if not date:
        return ""
    diff = (datetime.datetime.now() - date).total_seconds()
    if diff < 3600:  # < 1h
        return str(int(diff//60)) + "m"
    if diff < 86400:  # < 1d
        return str(int(diff//3600)) + "h"
    return str(int(diff//86400)) + "d"


def create_app(dbfile):
    template_folder = os.path.join(os.path.dirname(__file__), 'templates')
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True,
                template_folder=template_folder)
    app.config.from_mapping(
        DBFILE=dbfile,
    )
    app.app_context().push()

    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    app.jinja_env.filters['docutils'] = _docutils_filter
    app.jinja_env.filters['age'] = _age_filter

    from . import browser
    app.register_blueprint(browser.bp)

    @app.route("/")
    def hello():
        return "Hello World!"

    return app


def start_app(db):
    app = create_app(db)
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
