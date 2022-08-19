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
import time
import typing as ty
from argparse import Namespace
from configparser import ConfigParser

import flask_babel
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
from gevent.pool import Pool
from gevent.pywsgi import LoggingLogAdapter, WSGIServer
from prometheus_client import Counter, Histogram
from werkzeug.exceptions import NotFound
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from flask_minify import minify
except ImportError:
    minify = None


import webmon2
from webmon2 import database, worker

from . import _commons as c
from . import (
    _filters,
    appsession,
    atom,
    entries,
    entry,
    group,
    proxy,
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
    app.register_blueprint(proxy.BP)


def _start_bg_tasks(args: Namespace) -> None:
    cworker = worker.CheckWorker(args.workers)
    cworker.start()


_CSP = (
    "default-src 'self' 'unsafe-inline'; "
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
        SESSION_TYPE="db",
        APPLICATION_ROOT=web_root,
        SEND_FILE_MAX_AGE_DEFAULT=60 * 60 * 24 * 7,
        LANGUAGES=["en", "pl"],
        BABEL_TRANSLATION_DIRECTORIES="../translations",
    )
    app.config["app_conf"] = conf
    app.app_context().push()

    app.session_interface = appsession.DBSessionInterface(True)  # type: ignore
    babel = flask_babel.Babel(app)

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
        path = request.path
        # pages that not need valid user and don't need additional data like
        # locale setting
        if (
            path == "/favicon.ico"
            or path.startswith("/metrics")
            or path.startswith("/atom")
        ):
            return None

        if not _check_csrf_token():
            return abort(400)

        user_id = session.get("user")
        if user_id is not None:
            # user is logged
            # path that not need load additional data
            if (
                path.startswith("/binary/")
                or path.startswith("/static")
                or path == "/manifest.json"
                or path.startswith("/entry/mark/")
            ):
                return None

            if request.method == "GET":
                _count_unread(user_id)

            g.locale = str(flask_babel.get_locale())

            return None

        # pages that not need valid user
        if path.startswith("/sec/login"):
            return None

        # login is requred; redirect to login page

        # back url is registered only for get request to prevent bad request
        if request.method == "GET":
            session["_back_url"] = request.url
            session.modified = True

        return redirect(url_for("sec.login"))

    @app.after_request
    def after_request(  # pylint: disable=unused-variable
        resp: Response,
    ) -> Response:
        cont_type = (resp.content_type or "").partition(";")[0]
        if cont_type in (
            "application/json",
            "application/atom+xml",
            "text/plain",
        ):
            _set_cache_contol_no_cache(resp)

        if cont_type == "text/html":
            _set_cache_contol_no_cache(resp)
            resp.headers["Content-Security-Policy"] = _CSP
            resp.headers["X-Content-Type-Options"] = "nosniff"
            resp.headers["X-Frame-Options"] = "DENY"
        elif not resp.headers.get("Cache-Control"):
            resp.headers["Cache-Control"] = "public, max-age=31536000"

        resp_time = time.time() - request.req_start_time  # type: ignore
        _REQUEST_LATENCY.labels(request.endpoint, request.method).observe(
            resp_time
        )
        _REQUEST_COUNT.labels(
            request.method, request.endpoint, resp.status_code
        ).inc()
        return resp

    @app.context_processor
    def handle_context() -> ty.Dict[str, ty.Any]:
        """Inject object into jinja2 templates."""
        return {"webmon2": webmon2}

    @babel.localeselector
    def get_locale():
        return request.accept_languages.best_match(app.config["LANGUAGES"])

    @babel.timezoneselector
    def get_timezone():
        return session.get("_user_tz")

    return app


def _set_cache_contol_no_cache(resp: Response) -> None:
    if not resp.headers.get("Cache-Control"):
        resp.headers["Cache-Control"] = "no-cache, max-age=0"


def _check_csrf_token() -> bool:
    if request.method == "POST":
        req_token = request.form.get("_csrf_token")
        sess_token = session.get("_csrf_token")
        if req_token != sess_token:
            _LOG.info("bad csrf token")
            return False

    elif "_csrf_token" not in session:
        c.generate_csrf_token()

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
    buckets=[0.5, 1.0, 3.0, 10.0],
)


def create_app(args: Namespace, conf: ConfigParser) -> Flask:
    web_root = conf.get("web", "root")
    app = _create_app(args.debug, web_root, conf)

    if web_root != "/":
        app.wsgi_app = DispatcherMiddleware(  # type: ignore
            NotFound(), {web_root: app.wsgi_app}
        )

    app.wsgi_app = ProxyFix(  # type: ignore
        app.wsgi_app, x_proto=1, x_host=1, x_port=1, x_prefix=1
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
        http_server = WSGIServer(
            (host, port),
            app,
            spawn=pool,
            log=LoggingLogAdapter(logging.getLogger("werkzeug")),
        )
        http_server.serve_forever()
