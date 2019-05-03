#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Web gui application
"""

import os
import logging
import time

from flask import Flask, g, url_for, session, request, redirect
from werkzeug.wsgi import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from gevent.pywsgi import WSGIServer
from prometheus_client import Counter, Histogram


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
        request.req_start_time = time.time()
        if session.get('user') is None and \
                request.path not in('/sec/login', '/metrics'):
            return redirect(url_for('sec.login', back=request.url))
        return None

    @app.after_request
    def record_request_data(response):
        resp_time = time.time() - request.req_start_time
        _REQUEST_LATENCY.labels(request.endpoint, request.method).\
            observe(resp_time)
        _REQUEST_COUNT.labels(request.method, request.endpoint,
                              response.status_code).inc()
        return response

    return app


_REQUEST_COUNT = Counter(
    'webmon2_request_count', 'App Request Count',
    ['endpoint', 'method', 'http_status']
)
_REQUEST_LATENCY = Histogram(
    'webmon2_request_latency_seconds',
    'Request latency',
    ['endpoint', 'method'],
    buckets=[0.01, 0.1, 0.5, 1.0, 3.0, 10.0]
)


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
