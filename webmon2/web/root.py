#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Web gui
"""

import logging
import typing as ty

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, session,
    Response
)

from webmon2.web import get_db
import prometheus_client


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('root', __name__, url_prefix='/')


@BP.route('/')
def index():
    return redirect(url_for("entries.entries_unread"))


@BP.route('/sources')
def sources():
    db = get_db()
    user_id = session['user']
    return render_template("sources.html", sources=db.get_sources(user_id))


@BP.route("/sources/refresh")
def sources_refresh():
    db = get_db()
    updated = db.refresh()
    flash("{} sources mark to refresh".format(updated))
    return redirect(request.headers.get('Referer')
                    or url_for("root.sources"))


@BP.route("/sources/refresh/errors")
def sources_refresh_err():
    db = get_db()
    updated = db.refresh_errors()
    flash("{} sources with errors mark to refresh".format(updated))
    return redirect(request.headers.get('Referer')
                    or url_for("root.sources"))


@BP.route("/groups")
def groups():
    db = get_db()
    user_id = session['user']
    return render_template("groups.html", groups=db.get_groups(user_id))



@BP.route('/metrics')
def metrics():
    return Response(prometheus_client.generate_latest(),
                    mimetype='text/plain; version=0.0.4; charset=utf-8')
