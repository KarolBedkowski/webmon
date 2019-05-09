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
    Blueprint, render_template, redirect, url_for, request
)

from webmon2.web import get_db
from webmon2 import database

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('entry', __name__, url_prefix='/entry')


@BP.route("/<int:entry_id>")
def entry(entry_id):
    db = get_db()
    entry_ = database.entries.get(db, entry_id, with_source=True,
                                  with_group=True)
    if not entry_.read_mark:
        database.entries.mark_read(db, entry_id=entry_id)
        entry_.read_mark = 1
    return render_template("entry.html", entry=entry_)


# @BP.route("/<int:entry_id>/mark/read")
# def entry_mark_read(entry_id):
#     db = get_db()
#     database.entries.mark_read(db, entry_id=entry_id)
#     db.commit()
#     return redirect(request.headers.get('Referer')
#                     or url_for("root.sources"))


@BP.route('/mark/read', methods=["POST"])
def entry_mark_read_api():
    db = get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form['value']
    updated = database.entries.mark_read(
        db, entry_id=entry_id, read=state == 'read')
    db.commit()
    return state if updated else ""


@BP.route('/mark/star', methods=["POST"])
def entry_mark_star_api():
    db = get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form['value']
    updated = database.entries.mark_star(db, entry_id, star=state == 'star')
    db.commit()
    return state if updated else ""
