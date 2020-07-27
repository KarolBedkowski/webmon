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
import random

from flask import Flask, g, url_for, session, request, redirect, abort
try:
    from werkzeug.wsgi import DispatcherMiddleware
except ImportError:
    from wsgizeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix
from gevent.pywsgi import WSGIServer
from prometheus_client import Counter, Histogram

from webmon2 import database, worker


_LOG = logging.getLogger(__name__)


def _register_blueprints(app):
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

    from . import atom
    app.register_blueprint(atom.BP)


def _start_bg_tasks(args):
    cworker = worker.CheckWorker(args.workers)
    cworker.start()


_CSP = ("default-src 'self' 'unsafe-inline'; "
        "img-src *; media-src *; "
        "frame-src *; "
        "worker-src 'self' 'unsafe-inline' *; ")


def create_app(debug, root, args):
    template_folder = os.path.join(os.path.dirname(__file__), 'templates')
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True,
                template_folder=template_folder)
    app.config.from_mapping(
        ENV="debug" if debug else 'production',
        SECRET_KEY=b'rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf\xdf\xcc',
        SECURITY_PASSWORD_SALT=b'rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf',
        APPLICATION_ROOT=root,
        SEND_FILE_MAX_AGE_DEFAULT=60 * 60 * 24 * 7,
    )
    app.app_context().push()

    _register_blueprints(app)

    @app.teardown_appcontext
    def close_connection(_exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    @app.before_request
    def before_request():
        request.req_start_time = time.time()
        if not _check_csrf_token():
            return abort(400)
        path = request.path
        g.non_action = (path.startswith('/static')
                        or path.startswith('/sec/login')
                        or path.startswith('/metrics')
                        or path.startswith('/atom'))
        if g.non_action:
            return None
        user_id = session.get('user')
        if user_id is None:
            return redirect(url_for('sec.login', back=request.url))
        _count_unread(user_id)
        return None

    @app.after_request
    def after_request(response):
        if hasattr(g, 'non_action') and not g.non_action:
            if 'Cache-Control' not in response.headers:
                response.headers['Cache-Control'] = \
                    'no-cache, max-age=0, must-revalidate, no-store'
            response.headers['Access-Control-Expose-Headers'] = 'X-CSRF-TOKEN'
            response.headers['X-CSRF-TOKEN'] = session['_csrf_token']
        response.headers['Content-Security-Policy'] = _CSP
        resp_time = time.time() - request.req_start_time
        _REQUEST_LATENCY.labels(request.endpoint, request.method).\
            observe(resp_time)
        _REQUEST_COUNT.labels(request.method, request.endpoint,
                              response.status_code).inc()
        return response

    return app


def _generate_csrf_token():
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(random.SystemRandom().choice(chars) for _ in range(32))


def _check_csrf_token():
    if request.method == 'POST':
        req_token = request.form.get('_csrf_token')
        sess_token = session.get('_csrf_token')
        if req_token != sess_token:
            _LOG.info("bad csrf token")
            return False
        session['_csrf_token'] = _generate_csrf_token()
        session.updated = True
    elif '_csrf_token' not in session:
        session['_csrf_token'] = _generate_csrf_token()
        session.updated = True
    return True


def _count_unread(user_id: int):
    from webmon2.web import get_db
    db = get_db()
    unread = database.entries.get_total_count(db, user_id, unread=True)
    request.entries_unread_count = unread


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


def _parse_listen_address(address):
    if not address or ':' not in address:
        return '127.0.0.1', 5000
    host, port = address.split(':', 1)
    try:
        port = int(port)
        if port < 0 or port > 65535:
            raise ValueError()
    except ValueError:
        _LOG.warning("invalid listen port %s, using default 5000", port)
    if not host:
        _LOG.warning("missing host; using 127.0.0.1 as listen address")
        host = '127.0.0.1'
    return host, port


def start_app(args):
    root = args.web_app_root
    app = create_app(args.debug, root, args)
    host, port = _parse_listen_address(args.web_address)

    if root != '/':
        app.wsgi_app = DispatcherMiddleware(simple_not_found,
                                            {root: app.wsgi_app})
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1,
                            x_host=0, x_port=0, x_prefix=0)
    if args.debug:
        app.run(host=host, port=port, debug=True)
    else:
        http_server = WSGIServer((host, port), app)
        http_server.serve_forever()
