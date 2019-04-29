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
    Blueprint, render_template, redirect, url_for, request, flash, session
)

from webmon2.web import get_db, _commons as c
from webmon2 import model
from . import forms


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('group', __name__, url_prefix='/group')


@BP.route("/group/<int:group_id>/refresh")
def refresh_group(group_id):
    db = get_db()
    db.refresh(group_id=group_id)
    flash("Group mark to refresh")
    return redirect(request.headers.get('Referer')
                    or url_for("root.groups"))


@BP.route("/group/new")
@BP.route("/group/<int:group_id>", methods=["GET", "POST"])
def group_edit(group_id=0):
    db = get_db()
    sgroup = db.get_group(group_id) if group_id \
        else model.SourceGroup(user_id=session['user'])
    form = forms.GroupForm.from_model(sgroup)

    if request.method == 'POST':
        form.update_from_request(request.form)
        sgroup = form.update_model(sgroup)
        db.save_group(sgroup)
        return redirect(url_for("root.groups"))

    return render_template("group.html", group=sgroup)


@BP.route('/group/<int:group_id>/sources')
def group_sources(group_id: int):
    db = get_db()
    user_id = session['user']
    return render_template("group_sources.html",
                           group=db.get_group(group_id),
                           sources=list(db.get_sources(user_id, group_id)))


@BP.route("/group/<int:group_id>/entries")
@BP.route("/group/<int:group_id>/entries/<mode>")
@BP.route("/group/<int:group_id>/entries/<mode>/<int:page>")
def group_entries(group_id, mode=None, page=0):
    db = get_db()
    offset = (page or 0) * c.PAGE_LIMIT
    sgroup = db.get_group(group_id)
    user_id = session['user']
    entries = list(db.get_entries(user_id, group_id=group_id,
                                  unread=mode != 'all',
                                  limit=c.PAGE_LIMIT, offset=offset))
    total_entries = db.get_entries_total_count(
        session['user'], unread=False, group_id=group_id) \
        if mode == 'all' else len(entries)
    data = c.preprate_entries_list(entries, page, total_entries)
    return render_template(
        "group_entries.html",
        group=sgroup,
        showed='all' if mode == 'all' else None,
        **data)


@BP.route("/group/<int:group_id>/mark/read")
def group_mark_read(group_id):
    db = get_db()
    max_id = request.args.get('max_id')
    max_id = int(max_id) if max_id else max_id
    db.group_mark_read(group_id=group_id, max_id=max_id)
    if request.method == 'POST':
        return "ok"
    if request.args.get('go') == 'next':
        # go to next unread group
        group_id = db.get_next_unread_group(session['user'])
        _LOG.info("next group: %r", group_id)
        if group_id:
            return redirect(url_for('group.group_entries',
                                    group_id=group_id))
    return redirect(request.headers.get('Referer')
                    or url_for("root.groups"))
