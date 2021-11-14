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
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from webmon2 import common, database, model

from . import _commons as c
from . import forms

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint("group", __name__, url_prefix="/group")


@BP.route("/group/<int:group_id>/refresh")
def refresh_group(group_id: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    marked = database.sources.refresh(db, user_id, group_id=group_id)
    db.commit()
    flash(f"{marked} sources in group marked to refresh")
    return redirect(request.headers.get("Referer") or url_for("root.groups"))


@BP.route("/group/new", methods=["GET", "POST"])
@BP.route("/group/<int:group_id>", methods=["GET", "POST"])
def group_edit(group_id: int = 0) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    if group_id:
        try:
            sgroup = database.groups.get(db, group_id, user_id)
        except database.NotFound:
            return abort(404)
    else:
        sgroup = model.SourceGroup(user_id=user_id, name="")

    form = forms.GroupForm.from_model(sgroup)
    errors = {}
    entity_hash = str(hash(sgroup))

    if request.method == "POST":
        if entity_hash == request.form["_entity_hash"]:
            form.update_from_request(request.form)
            errors = form.validate()
            if not errors:
                usgroup = form.update_model(sgroup)
                database.groups.save(db, usgroup)
                db.commit()
                flash("Group saved")
                return redirect(
                    request.args.get("back") or url_for("root.groups")
                )
        else:
            flash("Group changed somewhere else; reloading...")

    return render_template(
        "group.html",
        group=form,
        group_id=group_id,
        errors=errors,
        entity_hash=entity_hash,
    )


@BP.route("/group/<int:group_id>/sources")
def group_sources(group_id: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    try:
        group = database.groups.get(db, group_id, user_id)
    except database.NotFound:
        return abort(404)

    status = request.args.get("status", "all")
    return render_template(
        "group_sources.html",
        group=group,
        sources=list(
            database.sources.get_all(db, user_id, group_id, status=status)
        ),
        status=status,
    )


@BP.route("/group/<int:group_id>/entries")
@BP.route("/group/<int:group_id>/entries/<mode>")
@BP.route("/group/<int:group_id>/entries/<mode>/<int:page>")
def group_entries(
    group_id: int, mode: str = "unread", page: int = 0
) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    try:
        sgroup = database.groups.get(db, group_id, user_id)
    except database.NotFound:
        return abort(404)

    order = request.args.get("order", "updated")
    offset = (page or 0) * c.PAGE_LIMIT
    mode = "all" if mode == "all" else "unread"
    unread = mode != "all"

    entries = list(
        database.entries.find(
            db,
            user_id,
            group_id=group_id,
            unread=unread,
            limit=c.PAGE_LIMIT,
            offset=offset,
        )
    )

    # total number of unread entries should be in globals
    total_entries = g.get("entries_unread_count")
    if total_entries is None or not unread:
        total_entries = database.entries.get_total_count(
            db, user_id, unread=unread, group_id=group_id
        )

    data = c.preprate_entries_list(entries, page, total_entries, order)

    return render_template(
        "group_entries.html", group=sgroup, showed=mode, **data
    )


@BP.route("/group/<int:group_id>/mark/read", methods=["POST"])
def group_mark_read(group_id: int) -> ty.Any:
    db = c.get_db()
    max_id = int(request.args.get("max_id", -1))
    min_id = int(request.args.get("min_id", -1))
    user_id = session["user"]
    ids: ty.Optional[ty.List[int]] = None
    r_ids = request.form.get("ids", "")
    if r_ids:
        ids = list(map(int, r_ids.split(","))) or None

    marked = database.groups.mark_read(
        db, user_id, group_id, min_id=min_id, max_id=max_id, ids=ids
    )
    db.commit()

    if request.args.get("go") == "next":
        # go to next unread group
        next_group_id = database.groups.get_next_unread_group(db, user_id)
        _LOG.debug("next group: %r", next_group_id)
        if next_group_id:
            return redirect(
                url_for("group.group_entries", group_id=next_group_id)
            )

        flash("No more unread groups...")
        dst = url_for("root.groups")
    else:
        dst = request.args.get("back") or url_for(
            "group.group_entries",
            group_id=group_id,
            page=request.args.get("page"),
            mode=request.args.get("mode"),
        )

    return {"url": dst, "marked": marked}


@BP.route("/group/<int:group_id>/next_unread")
def group_next_unread(group_id: int) -> ty.Any:
    db = c.get_db()
    # go to next unread group
    next_group_id = database.groups.get_next_unread_group(db, session["user"])
    _LOG.debug("next group: %r -> %r", group_id, next_group_id)
    if next_group_id:
        return redirect(url_for("group.group_entries", group_id=next_group_id))

    flash("No more unread groups...")
    return redirect(url_for("root.groups"))


@BP.route("/group/<int:group_id>/delete")
def group_delete(group_id: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    try:
        # sanity check
        database.groups.get(db, group_id, user_id)
        database.groups.delete(db, user_id, group_id)
        db.commit()
        flash("Group deleted")

    except database.NotFound:
        return abort(404)
    except common.OperationError as err:
        flash("Can't delete group: " + str(err), "error")

    if request.args.get("delete_self"):
        return redirect(url_for("root.groups"))

    return redirect(request.headers.get("Referer") or url_for("root.groups"))


@BP.route("/group/<int:group_id>/entry/<mode>/<int:entry_id>")
def group_entry(group_id: int, mode: str, entry_id: int) -> ty.Any:
    """Get entry by group view.
    Mark displayed items as manually read.

    @param mode: unread/all
    """
    db = c.get_db()
    user_id = session["user"]
    try:
        group = database.groups.get(db, group_id, user_id)
    except database.NotFound:
        return abort(404)

    entry = database.entries.get(
        db, entry_id, with_source=True, with_group=True
    )

    assert entry.source
    if user_id != entry.user_id or group_id != entry.source.group_id:
        return abort(404)

    if entry.read_mark == model.EntryReadMark.UNREAD:
        # mark entry as read
        database.entries.mark_read(
            db,
            user_id,
            entry_id=entry_id,
            read=model.EntryReadMark.MANUAL_READ,
        )
        entry.read_mark = model.EntryReadMark.MANUAL_READ
        db.commit()

    unread = mode != "all"
    next_entry = database.groups.find_next_entry_id(
        db, group_id, entry.id, unread
    )
    prev_entry = database.groups.find_prev_entry_id(
        db, group_id, entry.id, unread
    )
    return render_template(
        "group_entry.html",
        entry=entry,
        group_id=group_id,
        next_entry=next_entry,
        prev_entry=prev_entry,
        mode=mode,
        group=group,
    )
