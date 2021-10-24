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

import logging
import os
import random
import time
import typing as ty
from argparse import Namespace
from configparser import ConfigParser

from flask import (
    Flask,
    Response,
    abort,
    g,
    redirect,
    request,
    session,
    url_for,
)

try:
    from flask_minify import minify
except ImportError:
    minify = None

from gevent.pool import Pool
from gevent.pywsgi import WSGIServer
from prometheus_client import Counter, Histogram
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

from webmon2 import database, worker

from . import _commons as c
from . import (
    _filters,
    atom,
    entries,
    entry,
    group,
    root,
    security,
    source,
    system,
)

__all__ = ("create_app", "start_app")

_LOG = logging.getLogger(__name__)


def _register_blueprints(app: Flask) -> None:
    _filters.register(app)
    app.register_blueprint(root.BP)
    app.register_blueprint(entries.BP)
    app.register_blueprint(source.BP)
    app.register_blueprint(group.BP)
    app.register_blueprint(entry.BP)
    app.register_blueprint(system.BP)
    app.register_blueprint(security.BP)
    app.register_blueprint(atom.BP)


def _start_bg_tasks(args: Namespace) -> None:
    cworker = worker.CheckWorker(args.workers)
    cworker.start()


_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "img-src *; media-src *; "
    "frame-src *; "
    #    "form-action 'self'; "
    #    "base-url 'self'; "
    #    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "worker-src 'self' 'unsafe-inline' *; "
)


def _create_app(debug: bool, web_root: str, conf: ConfigParser) -> Flask:
    template_folder = os.path.join(os.path.dirname(__file__), "templates")
    # create and configure the app
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=template_folder,
    )

    if conf.getboolean("web", "minify"):
        if minify:
            minify(app=app, html=True, js=True, cssless=True)
        else:
            _LOG.warning("minifi enabled but flask_minifi is not installed!")

    app.config.from_mapping(
        ENV="debug" if debug else "production",
        SECRET_KEY=b"rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf\xdf\xcc",
        SECURITY_PASSWORD_SALT=b"rY\xac\xf9\x0c\xa6M\xffH\xb8h8\xc7\xcf",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Strict",
        APPLICATION_ROOT=web_root,
        SEND_FILE_MAX_AGE_DEFAULT=60 * 60 * 24 * 7,
    )
    app.config["app_conf"] = conf
    app.app_context().push()

    _register_blueprints(app)

    # @app.teardown_appcontext
    @app.teardown_request  # type: ignore
    def teardown_db(  # pylint: disable=unused-variable
        _exception: ty.Optional[BaseException],
    ) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.before_request
    def before_request() -> ty.Any:  # pylint: disable=unused-variable
        request.req_start_time = time.time()  # type: ignore
        if not _check_csrf_token():
            return abort(400)

        path = request.path
        g.non_action = (
            path.startswith("/static")
            or path.startswith("/sec/login")
            or path.startswith("/metrics")
            or path.startswith("/atom")
            or path.startswith("/binary/")
            or path == "/favicon.ico"
            or path == "/manifest.json"
        )
        if g.non_action or path.startswith("/entry/mark/"):
            return None

        user_id = session.get("user")
        if user_id is None:
            # back url is registered only for get request to prevent bad request
            if request.method == "GET":
                session["_back_url"] = request.url
                session.modified = True

            return redirect(url_for("sec.login"))

        if request.method == "GET":
            _count_unread(user_id)

        return None

    @app.after_request
    def after_request(  # pylint: disable=unused-variable
        resp: Response,
    ) -> Response:
        if hasattr(g, "non_action") and not g.non_action:
            if not resp.headers.get("Cache-Control"):
                resp.headers[
                    "Cache-Control"
                ] = "no-cache, max-age=0, must-revalidate, no-store"
            resp.headers["Access-Control-Expose-Headers"] = "X-CSRF-TOKEN"
            resp.headers["X-CSRF-TOKEN"] = str(session.get("_csrf_token"))
            resp.headers["Content-Security-Policy"] = _CSP
            resp.headers["X-Content-Type-Options"] = "nosniff"
            resp.headers["X-Frame-Options"] = "DENY"
        else:
            resp.headers["Cache-Control"] = "public, max-age=604800"

        resp_time = time.time() - request.req_start_time  # type: ignore
        _REQUEST_LATENCY.labels(request.endpoint, request.method).observe(
            resp_time
        )
        _REQUEST_COUNT.labels(
            request.method, request.endpoint, resp.status_code
        ).inc()
        return resp

    return app


def _generate_csrf_token() -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.SystemRandom().choice(chars) for _ in range(32))


def _check_csrf_token() -> bool:
    if request.method == "POST":
        req_token = request.form.get("_csrf_token")
        sess_token = session.get("_csrf_token")
        if req_token != sess_token:
            _LOG.info("bad csrf token")
            return False

        session["_csrf_token"] = _generate_csrf_token()
        session.modified = True

    elif "_csrf_token" not in session:
        session["_csrf_token"] = _generate_csrf_token()
        session.modified = True

    return True


def _count_unread(user_id: int) -> None:
    db = c.get_db()
    unread = database.entries.get_total_count(db, user_id, unread=True)
    g.entries_unread_count = unread


_REQUEST_COUNT = Counter(
    "webmon2_request_count",
    "App Request Count",
    ["endpoint", "method", "http_status"],
)
_REQUEST_LATENCY = Histogram(
    "webmon2_request_latency_seconds",
    "Request latency",
    ["endpoint", "method"],
    buckets=[0.01, 0.1, 0.5, 1.0, 3.0, 10.0],
)


def simple_not_found(_env: ty.Any, resp: Response) -> ty.Any:
    resp("400 Notfound", [("Content-Type", "text/plain")])
    return [b"Not found"]


def create_app(args: Namespace, conf: ConfigParser) -> Flask:
    web_root = conf.get("web", "root")
    app = _create_app(args.debug, web_root, conf)

    if web_root != "/":
        app.wsgi_app = DispatcherMiddleware(  # type: ignore
            simple_not_found, {web_root: app.wsgi_app}
        )

    app.wsgi_app = ProxyFix(  # type: ignore
        app.wsgi_app, x_proto=1, x_host=0, x_port=0, x_prefix=0
    )
    return app


def start_app(args: Namespace, conf: ConfigParser) -> None:
    app = create_app(args, conf)
    host = conf.get("web", "address")
    port = conf.getint("web", "port")
    if args.debug:
        app.run(host=host, port=port, debug=True)
    else:
        pool = Pool(conf.getint("web", "pool", fallback=10))
        http_server = WSGIServer((host, port), app, spawn=pool)
        http_server.serve_forever()
