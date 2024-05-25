# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Web gui
"""

from __future__ import annotations

import functools
import ipaddress
import typing as ty
from contextlib import suppress
from pathlib import Path

import prometheus_client
import psycopg
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
    send_from_directory,
    session,
    url_for,
)
from flask_babel import gettext, ngettext

from webmon2 import database

from . import _commons as c

BP = Blueprint("root", __name__, url_prefix="/")


@BP.route("/")  # type:ignore
def index() -> ty.Any:  # noqa: ANN401
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


@BP.route("/sources")  # type:ignore
def sources() -> ty.Any:  # noqa: ANN401
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


@BP.route("/sources/refresh")  # type:ignore
def sources_refresh() -> ty.Any:  # noqa: ANN401
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


@BP.route("/sources/refresh/errors")  # type:ignore
def sources_refresh_err() -> ty.Any:  # noqa: ANN401
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


@BP.route("/groups")  # type:ignore
def groups() -> ty.Any:  # noqa: ANN401
    db = c.get_db()
    user_id = session["user"]
    return render_template(
        "groups.html", groups=database.groups.get_all(db, user_id)
    )


@functools.cache
def _metrics_accesslist() -> (
    list[ipaddress.IPv4Network | ipaddress.IPv6Network]
):
    conf = current_app.config["app_conf"]
    networks = []
    for a in conf.get("metrics", "allow_from", fallback="").split(","):
        addr = a.strip()
        if "/" not in addr:
            addr = addr + "/32"

        networks.append(ipaddress.ip_network(addr, strict=False))

    return networks


def _is_address_allowed() -> bool:
    assert request.remote_addr
    if allowed_nets := _metrics_accesslist():
        for net in allowed_nets:
            if ipaddress.ip_address(request.remote_addr) in net:
                return True

        return False

    return True


@BP.route("/metrics")  # type:ignore
def metrics() -> ty.Any:  # noqa: ANN401
    if not _is_address_allowed():
        abort(401)

    return Response(
        prometheus_client.generate_latest(),
        mimetype="text/plain; version=0.0.4; charset=utf-8",
    )


@BP.route("/health")  # type:ignore
def health() -> ty.Any:  # noqa: ANN401
    return "ok"


@BP.route("/health/live")  # type:ignore
def health_live() -> ty.Any:  # noqa: ANN401
    if not _is_address_allowed():
        abort(401)

    with suppress(psycopg.OperationalError):
        db = c.get_db()
        if database.system.ping(db):
            return "ok"

    return abort(500)


@BP.route("/favicon.ico")  # type:ignore
def favicon() -> ty.Any:  # noqa: ANN401
    return send_from_directory(
        Path(current_app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@functools.cache
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
    return ty.cast(str, json.dumps(manifest))


@BP.route("/manifest.json")  # type:ignore
def manifest_json() -> Response:
    return Response(
        _build_manifest(), mimetype="application/manifest+json; charset=UTF-8"
    )


@BP.route("/binary/<datahash>")  # type:ignore
def binary(datahash: str) -> ty.Any:  # noqa: ANN401
    db = c.get_db()
    try:
        data_content_type = database.binaries.get(
            db, datahash, session["user"]
        )
    except database.NotFoundError:
        return abort(404)
    data, content_type = data_content_type
    resp = Response(data, mimetype=content_type)
    resp.headers["Cache-Control"] = "max-age=31536000, public, immutable"
    return resp
