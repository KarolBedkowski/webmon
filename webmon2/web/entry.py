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

from flask import Blueprint, abort, g, render_template, request, session
from flask_babel import gettext

from webmon2 import database, model

from . import _commons as c

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint("entry", __name__, url_prefix="/entry")


@BP.route("/<int:entry_id>")
def entry(entry_id: int) -> ty.Any:
    """Display entry and mark it as read."""
    db = c.get_db()
    user_id = session["user"]  # type: int
    entry_ = database.entries.get(
        db, entry_id, with_source=True, with_group=True
    )
    unread = entry_.read_mark == model.EntryReadMark.UNREAD
    if user_id != entry_.user_id:
        return abort(404)

    if entry_.read_mark == model.EntryReadMark.UNREAD:
        database.entries.mark_read(
            db,
            user_id,
            entry_id=entry_id,
            read=model.EntryReadMark.MANUAL_READ,
        )
        entry_.read_mark = model.EntryReadMark.MANUAL_READ
        g.entries_unread_count = database.entries.get_total_count(
            db, user_id, unread=True
        )
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
def entry_mark_read_api() -> ty.Any:
    """Mark entry read (by clicking on read mark)"""
    db = c.get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form["value"]
    user_id = session["user"]
    updated = database.entries.mark_read(
        db,
        user_id,
        entry_id=entry_id,
        read=(
            model.EntryReadMark.MANUAL_READ
            if state == "read"
            else model.EntryReadMark.UNREAD
        ),
    )
    db.commit()

    read_state = state == "read"
    if updated:
        read_state = not read_state

    res = {
        "result": state if updated else "",
        "unread": database.entries.get_total_count(db, user_id, unread=True),
        "title": gettext("Read") if read_state else gettext("Unread"),
    }

    return res


@BP.route("/mark/star", methods=["POST"])
def entry_mark_star_api() -> ty.Any:
    db = c.get_db()
    entry_id = int(request.form["entry_id"])
    user_id = session["user"]
    state = request.form["value"]
    updated = database.entries.mark_star(
        db, user_id, entry_id, star=state == "star"
    )
    db.commit()

    star_state = state == "star"
    if updated:
        star_state = not star_state

    return {
        "result": state if updated else "",
        "title": gettext("Star") if star_state else gettext("Unstar"),
    }
