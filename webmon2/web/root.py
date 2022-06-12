#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Web gui
"""

import logging
import typing as ty

import prometheus_client
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    json,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import gettext, ngettext

from webmon2 import common, database

from . import _commons as c

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint("root", __name__, url_prefix="/")


@BP.route("/")
def index() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    if database.settings.get_value(
        db, "start_at_unread_group", user_id, False
    ):
        group_id = database.groups.get_next_unread_group(db, user_id)
        if group_id:
            return redirect(url_for("group.group_entries", group_id=group_id))
        flash(gettext("No more unread groups..."))
    return redirect(url_for("entries.entries", mode="unread"))


@BP.route("/sources")
def sources() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    status = request.args.get("status", "all")
    order = request.args.get("order", "name")
    return render_template(
        "sources.html",
        sources=database.sources.get_all(
            db, user_id, status=status, order=order
        ),
        status=status,
        order=order,
    )


@BP.route("/sources/refresh")
def sources_refresh() -> ty.Any:
    db = c.get_db()
    updated = database.sources.refresh(db, session["user"])
    db.commit()
    flash(
        ngettext(
            "One source mark to refresh",
            "%(updated)s sources mark to refresh",
            updated,
            updated=updated,
        )
    )
    return redirect(request.headers.get("Referer") or url_for("root.sources"))


@BP.route("/sources/refresh/errors")
def sources_refresh_err() -> ty.Any:
    db = c.get_db()
    updated = database.sources.refresh_errors(db, session["user"])
    db.commit()
    flash(
        ngettext(
            "One source mark to refresh",
            "%(updated)s sources mark to refresh",
            updated,
            updated=updated,
        )
    )
    return redirect(request.headers.get("Referer") or url_for("root.sources"))


@BP.route("/groups")
def groups() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    return render_template(
        "groups.html", groups=database.groups.get_all(db, user_id)
    )


@common.cache
def _metrics_accesslist() -> ty.List[str]:
    conf = current_app.config["app_conf"]
    return [
        ip.strip()
        for ip in conf.get("metrics", "allow_from", fallback="").split(",")
    ]


@BP.route("/metrics")
def metrics() -> ty.Any:
    if request.remote_addr not in _metrics_accesslist():
        abort(401)

    return Response(
        prometheus_client.generate_latest(),  # type: ignore
        mimetype="text/plain; version=0.0.4; charset=utf-8",
    )


@common.cache
def _build_manifest() -> str:
    manifest = {
        "name": "Webmon2",
        "short_name": "Webmon2",
        "start_url": url_for("root.index"),
        "display": "browser",
        "background_color": "#fff",
        "description": "Web monitoring application.",
        "lang": "en-EN",
        "scope": url_for("root.index"),
        "icons": [
            {
                "src": url_for("static", filename="favicon-16.png"),
                "sizes": "16x16",
                "type": "image/png",
            },
            {
                "src": url_for("static", filename="favicon-32.png"),
                "sizes": "32x32",
                "type": "image/png",
            },
            {
                "src": url_for("static", filename="icon-128.png"),
                "sizes": "128x128",
                "type": "image/png",
            },
            {
                "src": url_for("static", filename="icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": url_for("static", filename="icon.svg"),
                "sizes": "192x192",
                "type": "image/svg+xml",
            },
        ],
    }
    return json.dumps(manifest)


@BP.route("/manifest.json")
def manifest_json() -> Response:
    return Response(
        _build_manifest(), mimetype="application/manifest+json; charset=UTF-8"
    )


@BP.route("/binary/<datahash>")
def binary(datahash: str) -> ty.Any:
    db = c.get_db()
    try:
        data_content_type = database.binaries.get(
            db, datahash, session["user"]
        )
    except database.NotFound:
        return abort(404)
    data, content_type = data_content_type
    resp = Response(data, mimetype=content_type)
    resp.headers["Cache-Control"] = "max-age=31536000, public, immutable"
    return resp
