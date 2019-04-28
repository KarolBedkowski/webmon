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

from webmon2.web import get_db, _commons as c
from webmon2 import inputs, model, filters
from . import forms

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('source', __name__, url_prefix='/source')


@BP.route("/<int:source_id>/refresh")
def source_refresh(source_id):
    db = get_db()
    db.refresh(source_id=source_id)
    flash("Source mark to refresh")
    return redirect(request.headers.get('Referer')
                    or url_for("root.sources"))


@BP.route("/<int:source_id>/delete")
def source_delete(source_id):
    db = get_db()
    db.source_delete(source_id)
    flash("Source deleted")
    if request.args.get("delete_self"):
        return redirect(url_for("root.sources"))
    return redirect(request.headers.get('Referer')
                    or url_for("root.sources"))


@BP.route("/new", methods=['POST', 'GET'])
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
            return redirect(url_for("source.source_edit",
                                    source_id=source.id))
    return render_template("source_new.html", kind=kind, name=name,
                           kinds=inputs.enumerate_inputs())


@BP.route("/<int:source_id>/edit", methods=['POST', 'GET'])
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
                return redirect(url_for("source.source_filters",
                                        source_id=source.id))
            return redirect(url_for('root.sources'))

    return render_template(
        "source.html",
        groups=db.get_groups(),
        source=source_form,
        errors=errors
    )


@BP.route("/<int:source_id>/entries")
@BP.route("/<int:source_id>/entries/<mode>")
@BP.route("/<int:source_id>/entries/<mode>/<int:page>")
def source_entries(source_id, mode='unread', page=0):
    db = get_db()
    offset = (page or 0) * c.PAGE_LIMIT
    entries = list(db.get_entries(
        source_id=source_id, unread=mode == 'unread', limit=c.PAGE_LIMIT,
        offset=offset))
    total_entries = db.get_entries_total_count(
        unread=False, source_id=source_id) if mode == 'all' else len(entries)
    data = c.preprate_entries_list(entries, page, total_entries)
    return render_template(
        "source_entries.html",
        source=db.get_source(source_id, with_group=True),
        showed='all' if mode == 'all' else 'unread',
        **data
        )


@BP.route("/<int:source_id>/mark/read")
def source_mark_read(source_id):
    db = get_db()
    max_id = int(request.args['max_id'])
    db.source_mark_read(source_id=source_id, max_id=max_id)
    if request.method == 'POST':
        return "ok"
    return redirect(request.headers.get('Referer')
                    or url_for("entries.unread"))


@BP.route("/<int:source_id>/filters")
def source_filters(source_id):
    db = get_db()
    source = db.get_source(source_id)
    filter_fields = [
        forms.Filter(fltr['name'])
        for fltr in source.filters or []
    ]
    return render_template("source_filters.html",
                           source=source,
                           filters=filter_fields)


@BP.route("/<int:source_id>/filter/add")
def source_filter_add(source_id):
    filter_names = filters.filter_names()
    return render_template("filter_new.html",
                           source_id=source_id,
                           filter_names=filter_names)


@BP.route("/<int:source_id>/filter/<idx>/edit", methods=['GET', 'POST'])
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
        return redirect(url_for("source.source_filters", source_id=source_id))

    settings = [forms.Field.from_input_params(
        param, conf) for param in fltr.params]
    return render_template("filter_edit.html",
                           filter=conf,
                           source=source,
                           settings=settings)


@BP.route("/<int:source_id>/filter/<int:idx>/move/<move>")
def source_filter_move(source_id, idx, move):
    db = get_db()
    db.source_move_filter(source_id, idx, move)
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/<int:source_id>/filter/<int:idx>/delete")
def source_filter_delete(source_id, idx):
    db = get_db()
    db.source_delete_filter(source_id, idx)
    return redirect(url_for("source.source_filters", source_id=source_id))
