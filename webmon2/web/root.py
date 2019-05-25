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

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, session,
    Response, json, abort
)
import prometheus_client

from webmon2.web import get_db
from webmon2 import database


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('root', __name__, url_prefix='/')


@BP.route('/')
def index():
    return redirect(url_for("entries.entries", mode='unread'))


@BP.route('/sources')
def sources():
    db = get_db()
    user_id = session['user']
    return render_template("sources.html",
                           sources=database.sources.get_all(db, user_id))


@BP.route("/sources/refresh")
def sources_refresh():
    db = get_db()
    updated = database.sources.refresh(db, session['user'])
    db.commit()
    flash("{} sources mark to refresh".format(updated))
    return redirect(request.headers.get('Referer')
                    or url_for("root.sources"))


@BP.route("/sources/refresh/errors")
def sources_refresh_err():
    db = get_db()
    updated = database.sources.refresh_errors(db, session['user'])
    db.commit()
    flash("{} sources with errors mark to refresh".format(updated))
    return redirect(request.headers.get('Referer')
                    or url_for("root.sources"))


@BP.route("/groups")
def groups():
    db = get_db()
    user_id = session['user']
    return render_template("groups.html",
                           groups=database.groups.get_all(db, user_id))


@BP.route('/metrics')
def metrics():
    return Response(prometheus_client.generate_latest(),
                    mimetype='text/plain; version=0.0.4; charset=utf-8')


_MANIFEST = None


@BP.route('/manifest.json')
def manifest_json():
    global _MANIFEST
    if not _MANIFEST:
        manifest = {
            "name": "Webmon2",
            "short_name": "Webmon2",
            "start_url": url_for("root.index"),
            "display": "browser",
            "background_color": "#fff",
            "description": "Web monitoring application.",
            "lang": "en-EN",
            "scope": url_for("root.index"),
            "icons": [{
                "src": url_for('static', filename='favicon-16.png'),
                "sizes": "16x16",
                "type": "image/png"
            }, {
                "src": url_for('static', filename='favicon-32.png'),
                "sizes": "32x32",
                "type": "image/png"
            }, {
                "src": url_for('static', filename='icon-128.png'),
                "sizes": "128x128",
                "type": "image/png"
            }, {
                "src": url_for('static', filename='icon-192.png'),
                "sizes": "192x192",
                "type": "image/png"
            }, {
                "src": url_for('static', filename='icon.svg'),
                "sizes": "192x192",
                "type": "image/svg+xml"
            }],
        }
        _MANIFEST = json.dumps(manifest)
    return Response(_MANIFEST, mimetype="application/manifest+json")


@BP.route('/binary/<datahash>')
def binary(datahash):
    db = get_db()
    data, content_type = database.binaries.get(db, datahash, session['user'])
    if not data:
        return abort(404)
    return Response(data, mimetype=content_type)
