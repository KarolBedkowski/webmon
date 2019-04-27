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
import logging

from flask import Flask, g, url_for, session, request, redirect
from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from gevent.pywsgi import WSGIServer
import markdown2


_LOG = logging.getLogger(__name__)


def _format_body_filter(body):
    if not body:
        return body
#    return publish_parts(
#        body, writer_name='html', settings=None)['fragment']
    return markdown2.markdown(body)


def _age_filter(date):
    if date is None:
        return ""
    diff = (datetime.datetime.now() - date).total_seconds()
    if diff < 60:
        return '<1m'
    if diff < 3600:  # < 1h
        return str(int(diff//60)) + "m"
    if diff < 86400:  # < 1d
        return str(int(diff//3600)) + "h"
    return str(int(diff//86400)) + "d"


def create_app(dbfile, debug, root):
    template_folder = os.path.join(os.path.dirname(__file__), 'templates')
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True,
                template_folder=template_folder)
    app.config.from_mapping(
        DBFILE=dbfile,
        SECRET_KEY=b'rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf\xdf\xcc',
        SECURITY_PASSWORD_SALT=b'rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf',
        APPLICATION_ROOT=root,
    )
    app.app_context().push()

    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    app.jinja_env.filters['format_body'] = _format_body_filter
    app.jinja_env.filters['age'] = _age_filter

    from . import browser
    app.register_blueprint(browser.BP)

    from . import system
    app.register_blueprint(system.BP)

    from . import security
    app.register_blueprint(security.BP)

    @app.route("/")
    def hello():
        return "Hello World!"

    @app.before_request
    def login_required():
        if session.get('user') is None and \
                request.path != '/sec/login':
            return redirect(url_for('sec.login', back=request.url))

    return app


def simple_not_found(env, resp):
    resp('400 Notfound', [('Content-Type', 'text/plain')])
    return [b'Not found']


def start_app(db, debug, root):
    app = create_app(db, debug, root)
    _LOG.info("app conf: %r", app.config)
    if root != '/':
        app.wsgi_app = DispatcherMiddleware(simple_not_found,
                                            {root: app.wsgi_app})
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    if debug:
        app.run(debug=True)
    else:
        http_server = WSGIServer(('', 5000), app)
        http_server.serve_forever()
