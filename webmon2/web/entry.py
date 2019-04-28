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
    Blueprint, render_template, redirect, url_for, request
)

from webmon2.web import get_db


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('entry', __name__, url_prefix='/entry')


@BP.route("/<int:entry_id>")
def entry(entry_id):
    db = get_db()
    entry_ = db.get_entry(entry_id)
    return render_template("entry", entry=entry_)


@BP.route("/<int:entry_id>/mark/read")
def entry_mark_read(entry_id):
    db = get_db()
    db.mark_read(entry_id=entry_id)
    return redirect(request.headers.get('Referer')
                    or url_for("browser.sources"))


@BP.route('/mark/read', methods=["POST"])
def entry_mark_read_api():
    db = get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form['value']
    updated = db.mark_read(entry_id=entry_id, read=state == 'read')
    return state if updated else ""


@BP.route('/mark/star', methods=["POST"])
def entry_mark_star_api():
    db = get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form['value']
    updated = db.mark_star(entry_id=entry_id, star=state == 'star')
    return state if updated else ""
