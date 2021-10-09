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

from flask import Blueprint, abort, render_template, request, session

from webmon2 import database, model

from . import _commons as c

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint("entry", __name__, url_prefix="/entry")


@BP.route("/<int:entry_id>")
def entry(entry_id: int):
    db = c.get_db()
    user_id = session["user"]  # type: int
    entry_ = database.entries.get(
        db, entry_id, with_source=True, with_group=True
    )
    unread = entry_.read_mark == 0
    if user_id != entry_.user_id:
        return abort(404)

    if not entry_.read_mark:
        database.entries.mark_read(
            db, user_id, entry_id=entry_id, read=model.EntryReadMark.READ
        )
        entry_.read_mark = model.EntryReadMark.READ
        db.commit()

    next_entry = database.entries.find_next_entry_id(
        db, user_id, entry_.id, unread
    )
    prev_entry = database.entries.find_prev_entry_id(
        db, user_id, entry_.id, unread
    )

    return render_template(
        "entry.html",
        entry=entry_,
        next_entry=next_entry,
        prev_entry=prev_entry,
    )


@BP.route("/mark/read", methods=["POST"])
def entry_mark_read_api():
    db = c.get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form["value"]
    user_id = session["user"]
    updated = database.entries.mark_read(
        db,
        user_id,
        entry_id=entry_id,
        read=(
            model.EntryReadMark.READ
            if state == "read"
            else model.EntryReadMark.UNREAD
        ),
    )
    db.commit()
    return state if updated else ""


@BP.route("/mark/star", methods=["POST"])
def entry_mark_star_api():
    db = c.get_db()
    entry_id = int(request.form["entry_id"])
    user_id = session["user"]
    state = request.form["value"]
    updated = database.entries.mark_star(
        db, user_id, entry_id, star=state == "star"
    )
    db.commit()
    return state if updated else ""
