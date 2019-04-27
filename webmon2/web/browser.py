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

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash
)

from webmon2.web import get_db
from webmon2 import inputs, model, filters
from . import forms


_LOG = logging.getLogger(__name__)
BP = Blueprint('browser', __name__, url_prefix='/')


@BP.route('/')
def index():
    return redirect(url_for("browser.entries_unread"))


@BP.route('/entries/unread')
def entries_unread():
    db = get_db()
    entries = list(db.get_unread_entries())
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("index.html", entries=entries, max_id=max_id,
                           showed_all=False)


@BP.route('/entries/all')
def entries_all():
    db = get_db()
    entries = list(db.get_entries(unread=False))
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("index.html", entries=entries, max_id=max_id,
                           showed_all=True)


@BP.route('/entries/starred')
def entries_starred():
    db = get_db()
    entries = list(db.get_starred_entries())
    return render_template("starred.html", entries=entries)


@BP.route('/entries/mark/read')
def entries_mark_read():
    db = get_db()
    db.mark_read(max_id=int(request.args['max_id']))
    return redirect(request.headers.get('Referer')
                    or url_for("browser.entries_unread"))


@BP.route('/sources')
def sources():
    db = get_db()
    return render_template("sources.html", sources=db.get_sources())


@BP.route("/sources/refresh")
def sources_refresh():
    db = get_db()
    db.refresh(refresh_all=True)
    flash("Sources mark to refresh")
    return redirect(request.headers.get('Referer')
                    or url_for("browser.sources"))


@BP.route("/source/<int:source_id>/refresh")
def source_refresh(source_id):
    db = get_db()
    db.refresh(source_id=source_id)
    flash("Source mark to refresh")
    return redirect(request.headers.get('Referer')
                    or url_for("browser.sources"))


@BP.route("/source/<int:source_id>/delete")
def source_delete(source_id):
    db = get_db()
    db.source_delete(source_id)
    flash("Source deleted")
    if request.args.get("delete_self"):
        return redirect(url_for("browser.sources"))
    return redirect(request.headers.get('Referer')
                    or url_for("browser.sources"))


@BP.route("/source/new", methods=['POST', 'GET'])
def source_new():
    kind = None
    name = ''
    if request.method == 'POST':
        kind = request.form['kind']
        name = request.form['name']
        if kind and name:
            db = get_db()
            source = model.Source()
            source.kind = kind
            source.name = name
            source = db.save_source(source)
            return redirect(url_for("browser.source_edit",
                                    source_id=source.id))
    return render_template("source_new.html", kind=kind, name=name,
                           kinds=inputs.enumerate_inputs())


@BP.route("/source/<int:source_id>/edit", methods=['POST', 'GET'])
def source_edit(source_id):
    db = get_db()
    source = db.get_source(source_id)
    inp = inputs.get_input(source, {})
    source_form = forms.SourceForm.from_model(source, inp.params)
    errors = {}

    if request.method == 'POST':
        source_form.update_from_request(request.form)
        errors = source_form.validate()
        if not errors:
            source = source_form.update_model(source)
            db.save_source(source)
            next_action = request.form.get("next_action")
            if next_action == 'edit_filters':
                return redirect(url_for("browser.source_filters",
                                        source_id=source.id))
            return redirect(url_for('browser.sources'))

    return render_template(
        "source.html",
        groups=db.get_groups(),
        source=source_form,
        errors=errors
    )


@BP.route("/source/<int:source_id>/entries/all")
def source_entries_all(source_id):
    db = get_db()
    entries = list(db.get_entries(source_id=source_id, unread=False))
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("source_entries.html",
                           entries=entries,
                           max_id=max_id,
                           source=db.get_source(source_id, with_group=True),
                           showed_all=True,
                           )


@BP.route("/source/<int:source_id>/entries")
def source_entries(source_id):
    db = get_db()
    entries = list(db.get_entries(source_id=source_id))
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("source_entries.html",
                           entries=entries,
                           max_id=max_id,
                           source=db.get_source(source_id, with_group=True),
                           showed_all=False,
                           )


@BP.route("/source/<int:source_id>/mark/read")
def source_mark_read(source_id):
    db = get_db()
    max_id = int(request.args['max_id'])
    db.mark_read(source_id=source_id, max_id=max_id)
    if request.method == 'POST':
        return "ok"
    return redirect(request.headers.get('Referer')
                    or url_for("browser.unread"))


@BP.route("/source/<int:source_id>/filters")
def source_filters(source_id):
    db = get_db()
    source = db.get_source(source_id)
    filters = [
        forms.Filter(fltr['name'])
        for fltr in source.filters or []
    ]
    return render_template("source_filters.html",
                           source=source,
                           filters=filters)


@BP.route("/source/<int:source_id>/filter/add")
def source_filter_add(source_id):
    filters_name = filters.filters_name()
    return render_template("filter_new.html",
                           source_id=source_id,
                           filters_name=filters_name)


@BP.route("/source/<int:source_id>/filter/<idx>/edit", methods=['GET', 'POST'])
def source_filter_edit(source_id, idx):
    db = get_db()
    source = db.get_source(source_id)
    idx = int(idx)
    if idx < 0 or idx >= len(source.filters or []):  # new filter
        conf = {'name': request.args['name']}
    else:
        conf = source.filters[idx]
    fltr = filters.get_filter(conf)
    if request.method == 'POST':
        param_types = fltr.get_param_types()
        for key, val in request.form.items():
            if key.startswith('sett-'):
                param_name = key[5:]
                if val:
                    param_type = param_types[param_name]
                    conf[param_name] = param_type(val)
                else:
                    conf[param_name] = None
        fltr = filters.get_filter(conf)
        fltr.validate()
        db.source_update_filter(source_id, idx, conf)
        return redirect(url_for("browser.source_filters", source_id=source_id))

    settings = [forms.Field.from_input_params(
        param, conf) for param in fltr.params]
    return render_template("filter_edit.html",
                           filter=conf,
                           source=source,
                           settings=settings)


@BP.route("/source/<int:source_id>/filter/<int:idx>/move/<move>")
def source_filter_move(source_id, idx, move):
    db = get_db()
    db.source_move_filter(source_id, idx, move)
    return redirect(url_for("browser.source_filters", source_id=source_id))


@BP.route("/source/<int:source_id>/filter/<int:idx>/delete")
def source_filter_delete(source_id, idx):
    db = get_db()
    db.source_delete_filter(source_id, idx)
    return redirect(url_for("browser.source_filters", source_id=source_id))


@BP.route("/groups")
def groups():
    db = get_db()
    return render_template("groups.html", groups=db.get_groups())


@BP.route("/group/new")
def group_new():
    return redirect(url_for("browser.group_edit", group_id=0))


@BP.route("/group/<int:group_id>/refresh")
def refresh_group(group_id):
    db = get_db()
    db.refresh(group_id=group_id)
    flash("Group mark to refresh")
    return redirect(request.headers.get('Referer')
                    or url_for("browser.groups"))


@BP.route("/group/<int:group_id>", methods=["GET", "POST"])
def group_edit(group_id):
    db = get_db()
    sgroup = db.get_group(group_id) if group_id else model.SourceGroup()
    form = forms.GroupForm.from_model(sgroup)

    if request.method == 'POST':
        form.update_from_request(request.form)
        sgroup = form.update_model(sgroup)
        db.save_group(sgroup)
        return redirect(url_for("browser.groups"))

    return render_template("group.html", group=sgroup)


@BP.route('/group/<int:group_id>/sources')
def group_sources(group_id: int):
    db = get_db()
    return render_template("group_sources.html",
                           group=db.get_group(group_id),
                           sources=list(db.get_sources(group_id)))


@BP.route("/group/<int:group_id>/entries")
def group_entries(group_id):
    db = get_db()
    sgroup = db.get_group(group_id)
    entries = list(db.get_entries(group_id=group_id))
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("group_entries.html", entries=entries,
                           max_id=max_id, group=sgroup, showed_all=False)


@BP.route("/group/<int:group_id>/entries/all")
def group_entries_all(group_id):
    db = get_db()
    sgroup = db.get_group(group_id)
    entries = list(db.get_entries(group_id=group_id, unread=False))
    max_id = max(entry.id for entry in entries) if entries else None
    return render_template("group_entries.html", entries=entries,
                           max_id=max_id, group=sgroup, showed_all=True)


@BP.route("/group/<int:group_id>/mark/read")
def group_mark_read(group_id):
    db = get_db()
    max_id = request.args.get('max_id')
    max_id = int(max_id) if max_id else max_id
    db.mark_read(group_id=group_id, max_id=max_id)
    if request.method == 'POST':
        return "ok"
    if request.args.get('go') == 'next':
        # go to next unread group
        group_id = db.get_next_unread_group()
        _LOG.info("next group: %r", group_id)
        if group_id:
            return redirect(url_for('browser.group_entries',
                                    group_id=group_id))
    return redirect(request.headers.get('Referer')
                    or url_for("browser.groups"))


@BP.route("/entry/<int:entry_id>")
def entry(entry_id):
    db = get_db()
    entry_ = db.get_entry(entry_id)
    return render_template("entry", entry=entry_)


@BP.route("/entry/<int:entry_id>/mark/read")
def entry_mark_read(entry_id):
    db = get_db()
    db.mark_read(entry_id=entry_id)
    return redirect(request.headers.get('Referer')
                    or url_for("browser.sources"))


@BP.route('/entry/mark/read', methods=["POST"])
def entry_mark_read_api():
    db = get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form['value']
    updated = db.mark_read(entry_id=entry_id, read=state == 'read')
    return state if updated else ""


@BP.route('/entry/mark/star', methods=["POST"])
def entry_mark_star_api():
    db = get_db()
    entry_id = int(request.form["entry_id"])
    state = request.form['value']
    updated = db.mark_star(entry_id=entry_id, star=state == 'star')
    return state if updated else ""
