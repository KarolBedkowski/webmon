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
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from webmon2 import database, model

from . import _commons as c

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint("entries", __name__, url_prefix="/entries")


@BP.route("/")
def index() -> ty.Any:
    return redirect(url_for("entries.entries", mode="unread"))


@BP.route("/<mode>/", defaults={"page": 0})
@BP.route("/<mode>/<int:page>")
def entries(mode: str, page: int) -> ty.Any:
    if mode not in ("unread", "all"):
        raise ValueError("invalid mode")

    db = c.get_db()
    limit, offset = c.PAGE_LIMIT, page * c.PAGE_LIMIT
    unread = mode == "unread"
    user_id = session["user"]
    order = request.args.get("order", "name")
    total_entries = database.entries.get_total_count(
        db, user_id, unread=unread
    )
    entries_ = list(
        database.entries.find(
            db, user_id, limit=limit, offset=offset, unread=unread, order=order
        )
    )
    data = c.preprate_entries_list(entries_, page, total_entries, order)
    return render_template("entries.html", showed=mode, **data)


@BP.route("/starred")
def entries_starred() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    entries_ = list(database.entries.get_starred(db, user_id))
    return render_template("starred.html", entries=entries_)


@BP.route("/history")
def entries_history() -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    entries_ = list(database.entries.get_history(db, user_id))
    return render_template("history.html", entries=entries_)


def _get_req_source(
    db: database.DB, user_id: int
) -> ty.Optional[model.Source]:
    try:
        source_id = int(request.args.get("source_id", "0"))
        if not source_id:
            return None

    except (ValueError, TypeError, KeyError) as err:
        _LOG.debug("req source error: %s", err)
        return None

    return database.sources.get(
        db, source_id, with_state=False, with_group=False, user_id=user_id
    )


def _get_req_group(
    db: database.DB, user_id: int
) -> ty.Optional[model.SourceGroup]:
    try:
        group_id = int(request.args.get("group_id", "0"))
        if not group_id:
            return None

    except (ValueError, TypeError, KeyError) as err:
        _LOG.debug("req group error: %s", err)
        return None

    return database.groups.get(db, group_id, user_id)


@BP.route("/search")
def entries_search() -> str:
    db = c.get_db()
    user_id = session["user"]  # type: int
    query = request.args.get("query", "").strip()
    title_only = bool(request.args.get("title-only"))
    search_ctx = ""
    source = _get_req_source(db, user_id)
    source_id, group_id = None, None
    if source:
        search_ctx = "in source: " + source.name
        source_id = source.id
    else:
        group = _get_req_group(db, user_id)
        if group:
            search_ctx = "in group: " + group.name
            group_id = group.id

    entries_ = None
    if query:
        entries_ = list(
            database.entries.find_fulltext(
                db, user_id, query, title_only, group_id, source_id
            )
        )

    return render_template(
        "entries_search.html",
        entries=entries_,
        query=query,
        title_only=title_only,
        group_id=group_id or "",
        source_id=source_id or "",
        search_ctx=search_ctx,
    )


@BP.route("/<mode>/mark/read")
def entries_mark_read(mode: str) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]  # type: int
    ids = [int(id_) for id_ in request.args.get("ids", "").split(",")] or None
    marked = database.entries.mark_read(
        db,
        user_id,
        max_id=int(request.args["max_id"]),
        min_id=int(request.args["min_id"]),
        ids=ids,
    )
    db.commit()
    flash(f"{marked} entries marked read")
    return redirect(url_for("entries.entries", mode=mode))
