#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Web gui application
"""

import os
import logging

from flask import Flask, g, url_for, session, request, redirect
from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from gevent.pywsgi import WSGIServer


_LOG = logging.getLogger(__name__)


def create_app(debug, root):
    template_folder = os.path.join(os.path.dirname(__file__), 'templates')
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True,
                template_folder=template_folder)
    app.config.from_mapping(
        ENV="debug" if debug else 'production',
        SECRET_KEY=b'rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf\xdf\xcc',
        SECURITY_PASSWORD_SALT=b'rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf',
        APPLICATION_ROOT=root,
    )
    app.app_context().push()

    @app.teardown_appcontext
    def close_connection(_exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    from . import _filters
    _filters.register(app)

    from . import root
    app.register_blueprint(root.BP)

    from . import entries
    app.register_blueprint(entries.BP)

    from . import source
    app.register_blueprint(source.BP)

    from . import group
    app.register_blueprint(group.BP)

    from . import entry
    app.register_blueprint(entry.BP)

    from . import system
    app.register_blueprint(system.BP)

    from . import security
    app.register_blueprint(security.BP)

    @app.before_request
    def login_required():
        if session.get('user') is None and \
                request.path != '/sec/login':
            return redirect(url_for('sec.login', back=request.url))
        return None

    return app


def simple_not_found(_env, resp):
    resp('400 Notfound', [('Content-Type', 'text/plain')])
    return [b'Not found']


def start_app(debug, root):
    app = create_app(debug, root)
    if root != '/':
        app.wsgi_app = DispatcherMiddleware(simple_not_found,
                                            {root: app.wsgi_app})
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1,
                            x_host=0, x_port=0, x_prefix=0)
    if debug:
        app.run(debug=True)
    else:
        http_server = WSGIServer(('', 5000), app)
        http_server.serve_forever()
