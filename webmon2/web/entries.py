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
    Blueprint, render_template, redirect, url_for, request, session
)

from webmon2.web import get_db, _commons as c
from webmon2 import database


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('entries', __name__, url_prefix='/entries')


@BP.route('/')
def index():
    return redirect(url_for("entries.entries_unread"))


@BP.route('/unread')
def entries_unread():
    db = get_db()
    user_id = session['user']
    entries = list(database.entries.find(db, user_id, unread=True))
    min_id = min(entry.id for entry in entries) if entries else None
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("entries.html", showed='unread',
                           total_entries=len(entries),
                           min_id=min_id, max_id=max_id,
                           entries=entries)


@BP.route('/all/', defaults={'page': 0})
@BP.route('/all/<int:page>')
def entries_all(page):
    db = get_db()
    limit, offset = c.PAGE_LIMIT, page * c.PAGE_LIMIT
    user_id = session['user']
    total_entries = database.entries.get_total_count(db, user_id, unread=False)
    entries = list(database.entries.find(
        db, user_id, limit=limit, offset=offset, unread=False))
    data = c.preprate_entries_list(entries, page, total_entries)
    return render_template("entries.html", showed='all', **data)


@BP.route('/starred')
def entries_starred():
    db = get_db()
    user_id = session['user']
    entries = list(database.entries.list_starred(db, user_id))
    return render_template("starred.html", entries=entries)


@BP.route('/mark/read')
def entries_mark_read():
    db = get_db()
    user_id = session['user']
    database.entries.mark_read(
        db, user_id,
        max_id=int(request.args['max_id']),
        min_id=int(request.args['min_id']))
    _LOG.debug("Referer: %r", request.headers.get('Referer'))
    return redirect(request.headers.get('Referer')
                    or url_for("entries.entries_unread"))
