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
from webmon2 import sources, model, filters, database
from . import forms

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('source', __name__, url_prefix='/source')


@BP.route("/<int:source_id>/refresh")
def source_refresh(source_id):
    db = get_db()
    user_id = session['user']
    database.sources.refresh(db, user_id, source_id=source_id)
    db.commit()
    flash("Source mark to refresh")
    return redirect(request.args.get('back') or url_for("root.sources"))


@BP.route("/<int:source_id>/delete")
def source_delete(source_id):
    db = get_db()
    user_id = session['user']
    source = database.sources.get(db, source_id)
    if not source or source.user_id != user_id:
        return abort(404)
    database.sources.delete(db, source_id)
    db.commit()
    flash("Source deleted")
    return redirect(request.args.get('back') or url_for("root.sources"))


@BP.route("/new")
def source_new():
    return render_template("source_new.html", sources=sources.sources_info())


@BP.route("/<int:source_id>/edit", methods=['POST', 'GET'])
@BP.route("/new/<kind>", methods=["POST", "GET"])
def source_edit(source_id=None, kind=None):
    db = get_db()
    user_id = session['user']
    if source_id:
        source = database.sources.get(db, source_id, with_state=True)
        if not source or source.user_id != user_id:
            return abort(404)
    elif kind:
        source = model.Source(kind=kind, user_id=user_id, name='')
    else:
        return abort(400)
    src = sources.get_source(source, {})
    user_settings = database.settings.get_dict(db, source.user_id)
    source_form = forms.SourceForm.from_model(source)
    source_form.settings = [
        forms.Field.from_input_params(param, source.settings, 'sett-',
                                      user_settings.get(param.name))
        for param in src.params]
    errors = {}
    user_id = session['user']

    if request.method == 'POST':
        source_form.update_from_request(request.form)
        errors = source_form.validate()
        source = source_form.update_model(source)
        errors.update(src.validate_conf(source.settings, user_settings))
        if not errors:
            if source.status == 0:
                source.status = 1
            source = database.sources.save(db, source)
            db.commit()
            flash("Source saved")
            next_action = request.form.get("next_action")
            if next_action == 'edit_filters':
                return redirect(url_for("source.source_filters",
                                        source_id=source.id))
            return redirect(url_for('root.sources'))

    return render_template(
        "source.html",
        groups=database.groups.get_all(db, user_id),
        form=source_form,
        errors=errors,
        source_cls=src,
        source=source,
    )


@BP.route("/<int:source_id>/entries")
@BP.route("/<int:source_id>/entries/<mode>")
@BP.route("/<int:source_id>/entries/<mode>/<int:page>")
def source_entries(source_id, mode='unread', page=0):
    db = get_db()
    offset = (page or 0) * c.PAGE_LIMIT
    user_id = session['user']
    entries = list(database.entries.find(
        db, user_id, source_id=source_id, unread=mode == 'unread',
        limit=c.PAGE_LIMIT, offset=offset))
    total_entries = database.entries.get_total_count(
        db, user_id, unread=False, source_id=source_id) \
        if mode == 'all' else len(entries)
    data = c.preprate_entries_list(entries, page, total_entries)
    return render_template(
        "source_entries.html",
        source=database.sources.get(db, source_id, with_group=True),
        showed='all' if mode == 'all' else 'unread',
        **data)


@BP.route("/<int:source_id>/mark/read")
def source_mark_read(source_id):
    db = get_db()
    max_id = int(request.args['max_id'])
    user_id = session['user']
    database.sources.mark_read(db, user_id, source_id, max_id=max_id)
    db.commit()
    if request.method == 'POST':
        return "ok"
    return redirect(url_for("root.sources"))


@BP.route("/<int:source_id>/filters")
def source_filters(source_id):
    db = get_db()
    user_id = session['user']
    source = database.sources.get(db, source_id)
    if not source or source.user_id != user_id:
        return abort(404)
    _LOG.debug("source.filters: %s", source.filters)
    filter_fields = [
        forms.Filter(fltr['name'])
        for fltr in source.filters or []
    ]
    return render_template("source_filters.html",
                           source=source,
                           filters=filter_fields)


@BP.route("/<int:source_id>/filter/add")
def source_filter_add(source_id):
    filters_info = filters.filters_info()
    return render_template("filter_new.html",
                           source_id=source_id,
                           filters_info=filters_info)


@BP.route("/<int:source_id>/filter/<idx>/edit", methods=['GET', 'POST'])
def source_filter_edit(source_id, idx):
    db = get_db()
    source = database.sources.get(db, source_id)
    user_id = session['user']
    if not source or source.user_id != user_id:
        return abort(404)
    idx = int(idx)
    is_new = idx < 0 or idx >= len(source.filters or [])
    if is_new:  # new filter
        name = request.args.get('name')
        if not name:
            return redirect(url_for("source_filter_add", source_id=source_id))
        conf = {'name': request.args['name']}
    else:
        conf = source.filters[idx]

    fltr = filters.get_filter(conf)

    # for new filters without parameters, save it
    if is_new and not fltr.params:
        return _save_filter(db, source_id, idx, conf)

    errors = {}
    form = forms.FieldsForm(
        [forms.Field.from_input_params(param, conf, prefix='sett-')
         for param in fltr.params])

    if request.method == 'POST':
        form.update_from_request(request.form)
        conf.update(form.values_map())
        errors = dict(fltr.validate_conf(conf))
        if not errors:
            return _save_filter(db, source_id, idx, conf)

    return render_template("filter_edit.html", filter=conf, source=source,
                           form=form, errors=errors, fltr=fltr)


def _build_filter_conf_from_req(fltr, conf):
    param_types = fltr.get_param_types()
    for key, val in request.form.items():
        if key.startswith('sett-'):
            param_name = key[5:]
            if val:
                param_type = param_types[param_name]
                conf[param_name] = param_type(val)
            else:
                conf[param_name] = None
    return conf


def _save_filter(db, source_id, idx, conf):
    database.sources.update_filter(db, source_id, idx, conf)
    db.commit()
    flash("Filter saved")
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/<int:source_id>/filter/<int:idx>/move/<move>")
def source_filter_move(source_id, idx, move):
    db = get_db()
    user_id = session['user']
    database.sources.move_filter(db, user_id, source_id, idx, move)
    db.commit()
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/<int:source_id>/filter/<int:idx>/delete")
def source_filter_delete(source_id, idx):
    db = get_db()
    user_id = session['user']
    database.sources.delete_filter(db, user_id, source_id, idx)
    db.commit()
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/source/<int:source_id>/entry/<mode>/<int:entry_id>")
def source_entry(source_id, mode, entry_id):
    db = get_db()
    user_id = session['user']
    src = database.sources.get(db, source_id)
    if not src or src.user_id != user_id:
        return abort(404)
    entry = database.entries.get(db, entry_id, with_source=True,
                                 with_group=True)
    if user_id != entry.user_id or source_id != entry.source_id:
        return abort(404)
    if not entry.read_mark:
        database.entries.mark_read(db, user_id, entry_id=entry_id)
        entry.read_mark = 1
        db.commit()
    unread = mode != 'all'
    next_entry = database.sources.find_next_entry_id(
        db, source_id, entry.id, unread)
    prev_entry = database.sources.find_prev_entry_id(
        db, source_id, entry.id, unread)
    return render_template("source_entry.html", entry=entry,
                           source_id=source_id, next_entry=next_entry,
                           prev_entry=prev_entry,
                           mode=mode, source=src)


@BP.route("/source/<int:source_id>/next_unread")
def source_next_unread(source_id):
    db = get_db()
    source_id = database.sources.find_next_unread(db, session['user'])
    _LOG.info("next sources: %r", source_id)
    if source_id:
        return redirect(url_for('source.source_entries', source_id=source_id))
    flash("No more unread sources...")
    return redirect(url_for("root.sources"))
