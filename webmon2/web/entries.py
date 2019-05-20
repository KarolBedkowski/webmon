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
    Blueprint, render_template, redirect, url_for, request, session
)

from webmon2.web import get_db, _commons as c
from webmon2 import database


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('entries', __name__, url_prefix='/entries')


@BP.route('/')
def index():
    return redirect(url_for("entries.entries", mode='unread'))


@BP.route('/<mode>/', defaults={'page': 0})
@BP.route('/<mode>/<int:page>')
def entries(mode, page):
    assert mode in ('unread', 'all')
    db = get_db()
    limit, offset = c.PAGE_LIMIT, page * c.PAGE_LIMIT
    unread = mode == 'unread'
    user_id = session['user']
    total_entries = database.entries.get_total_count(db, user_id,
                                                     unread=unread)
    entries_ = list(database.entries.find(
        db, user_id, limit=limit, offset=offset, unread=unread))
    data = c.preprate_entries_list(entries_, page, total_entries)
    return render_template("entries.html", showed=mode, **data)


@BP.route('/starred')
def entries_starred():
    db = get_db()
    user_id = session['user']
    entries_ = list(database.entries.get_starred(db, user_id))
    return render_template("starred.html", entries=entries_)


@BP.route('/<mode>/mark/read')
def entries_mark_read(mode):
    db = get_db()
    user_id = session['user']
    database.entries.mark_read(
        db, user_id,
        max_id=int(request.args['max_id']),
        min_id=int(request.args['min_id']))
    db.commit()
    return redirect(url_for("entries.entries", mode=mode))
