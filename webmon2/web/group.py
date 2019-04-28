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
    Blueprint, render_template, redirect, url_for, request, flash
)

from webmon2.web import get_db
from webmon2 import model
from . import forms


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('group', __name__, url_prefix='/group')


@BP.route("/group/new")
def group_new():
    return redirect(url_for("group.group_edit", group_id=0))


@BP.route("/group/<int:group_id>/refresh")
def refresh_group(group_id):
    db = get_db()
    db.refresh(group_id=group_id)
    flash("Group mark to refresh")
    return redirect(request.headers.get('Referer')
                    or url_for("root.groups"))


@BP.route("/group/<int:group_id>", methods=["GET", "POST"])
def group_edit(group_id):
    db = get_db()
    sgroup = db.get_group(group_id) if group_id else model.SourceGroup()
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
    return render_template("group_sources.html",
                           group=db.get_group(group_id),
                           sources=list(db.get_sources(group_id)))


@BP.route("/group/<int:group_id>/entries")
@BP.route("/group/<int:group_id>/entries/<mode>")
def group_entries(group_id, mode=None):
    db = get_db()
    sgroup = db.get_group(group_id)
    entries = list(db.get_entries(group_id=group_id, unread=mode != 'all'))
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("group_entries.html", entries=entries,
                           max_id=max_id, group=sgroup,
                           showed_all=mode == 'all')


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
        group_id = db.get_next_unread_group()
        _LOG.info("next group: %r", group_id)
        if group_id:
            return redirect(url_for('group.group_entries',
                                    group_id=group_id))
    return redirect(request.headers.get('Referer')
                    or url_for("root.groups"))
