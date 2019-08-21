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
    abort
)

from webmon2.web import get_db, _commons as c
from webmon2 import model, database, common
from . import forms


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('group', __name__, url_prefix='/group')


@BP.route("/group/<int:group_id>/refresh")
def refresh_group(group_id):
    db = get_db()
    user_id = session['user']
    marked = database.sources.refresh(db, user_id, group_id=group_id)
    db.commit()
    flash(f"{marked} sources in group marked to refresh")
    return redirect(request.headers.get('Referer') or url_for("root.groups"))


@BP.route("/group/new", methods=["GET", "POST"])
@BP.route("/group/<int:group_id>", methods=["GET", "POST"])
def group_edit(group_id=0):
    db = get_db()
    user_id = session['user']
    if group_id:
        sgroup = database.groups.get(db, group_id)
        if not sgroup or sgroup.user_id != user_id:
            return abort(404)
    else:
        sgroup = model.SourceGroup(user_id=user_id)

    form = forms.GroupForm.from_model(sgroup)
    errors = {}
    if request.method == 'POST':
        form.update_from_request(request.form)
        errors = form.validate()
        if not errors:
            sgroup = form.update_model(sgroup)
            database.groups.save(db, sgroup)
            db.commit()
            flash("Group saved")
            return redirect(request.args.get('back') or url_for("root.groups"))

    return render_template("group.html", group=form, group_id=group_id,
                           errors=errors)


@BP.route('/group/<int:group_id>/sources')
def group_sources(group_id: int):
    db = get_db()
    user_id = session['user']
    group = database.groups.get(db, group_id)
    if group.user_id != user_id:
        return abort(404)
    return render_template(
        "group_sources.html",
        group=group,
        sources=list(database.sources.get_all(db, user_id, group_id)))


@BP.route("/group/<int:group_id>/entries")
@BP.route("/group/<int:group_id>/entries/<mode>")
@BP.route("/group/<int:group_id>/entries/<mode>/<int:page>")
def group_entries(group_id, mode='unread', page=0):
    db = get_db()
    sgroup = database.groups.get(db, group_id)
    user_id = session['user']

    if sgroup.user_id != user_id:
        return abort(404)

    offset = (page or 0) * c.PAGE_LIMIT
    mode = 'all' if mode == 'all' else 'unread'
    unread = mode != 'all'

    entries = list(database.entries.find(
        db, user_id, group_id=group_id, unread=unread,
        limit=c.PAGE_LIMIT, offset=offset))

    total_entries = database.entries.get_total_count(
        db, user_id, unread=unread, group_id=group_id)

    data = c.preprate_entries_list(entries, page, total_entries)

    return render_template("group_entries.html", group=sgroup,
                           showed=mode, **data)


@BP.route("/group/<int:group_id>/mark/read")
def group_mark_read(group_id):
    db = get_db()
    max_id = int(request.args.get('max_id', -1))
    min_id = int(request.args.get('min_id', -1))
    user_id = session['user']
    r_ids = request.args.get('ids')
    ids = list(map(int, r_ids.split(","))) if r_ids else None
    database.groups.mark_read(db, user_id, group_id, min_id=min_id,
                              max_id=max_id, ids=ids)
    db.commit()
    if request.args.get('go') == 'next':
        # go to next unread group
        group_id = database.groups.get_next_unread_group(db, user_id)
        _LOG.debug("next group: %r", group_id)
        if group_id:
            return redirect(url_for('group.group_entries', group_id=group_id))
        flash("No more unread groups...")
        return redirect(url_for("root.groups"))

    return redirect(request.args.get('back')
                    or url_for("group.group_entries",
                               group_id=group_id,
                               page=request.args.get('page'),
                               mode=request.args.get('mode')))


@BP.route("/group/<int:group_id>/next_unread")
def group_next_unread(group_id):
    db = get_db()
    # go to next unread group
    group_id = database.groups.get_next_unread_group(db, session['user'])
    _LOG.debug("next group: %r", group_id)
    if group_id:
        return redirect(url_for('group.group_entries', group_id=group_id))
    flash("No more unread groups...")
    return redirect(url_for("root.groups"))


@BP.route("/group/<int:group_id>/delete")
def group_delete(group_id):
    db = get_db()
    user_id = session['user']
    try:
        group_ = database.groups.get(db, group_id)
        if not group_ or group_.user_id != user_id:
            return abort(404)
        database.groups.delete(db, user_id, group_id)
        db.commit()
        flash("Group deleted")
    except common.OperationError as err:
        flash("Can't delete group: " + str(err), 'error')
    if request.args.get("delete_self"):
        return redirect(url_for("root.groups"))
    return redirect(request.headers.get('Referer') or url_for("root.groups"))


@BP.route("/group/<int:group_id>/entry/<mode>/<int:entry_id>")
def group_entry(group_id, mode, entry_id):
    db = get_db()
    user_id = session['user']
    group = database.groups.get(db, group_id)
    if not group or group.user_id != user_id:
        return abort(404)
    entry = database.entries.get(db, entry_id, with_source=True,
                                 with_group=True)
    if user_id != entry.user_id or group_id != entry.source.group_id:
        return abort(404)
    if not entry.read_mark:
        database.entries.mark_read(db, user_id, entry_id=entry_id, read=2)
        entry.read_mark = 2
        db.commit()
    unread = mode != 'all'
    next_entry = database.groups.find_next_entry_id(
        db, group_id, entry.id, unread)
    prev_entry = database.groups.find_prev_entry_id(
        db, group_id, entry.id, unread)
    return render_template("group_entry.html", entry=entry,
                           group_id=group_id, next_entry=next_entry,
                           prev_entry=prev_entry,
                           mode=mode, group=group)
