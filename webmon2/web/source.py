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
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import gettext

from webmon2 import common, database, filters, model, sources

from . import _commons as c
from . import forms

_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint("source", __name__, url_prefix="/source")


@BP.route("/<int:source_id>/refresh")
def source_refresh(source_id: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    database.sources.refresh(db, user_id, source_id=source_id)
    db.commit()
    flash(gettext("Source mark to refresh"))
    return redirect(request.args.get("back") or url_for("root.sources"))


@BP.route("/<int:source_id>/delete")
def source_delete(source_id: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    try:
        # sanity check (source vs user)
        database.sources.get(db, source_id, user_id=user_id)
    except database.NotFound:
        return abort(404)

    database.sources.delete(db, source_id)
    db.commit()
    flash(gettext("Source deleted"))
    return redirect(request.args.get("back") or url_for("root.sources"))


@BP.route("/new")
def source_new() -> ty.Any:
    return render_template("source_new.html", sources=sources.sources_info())


@BP.route("/<int:source_id>/edit", methods=["POST", "GET"])
@BP.route("/new/<kind>", methods=["POST", "GET"])
def source_edit(
    source_id: ty.Optional[int] = None, kind: ty.Optional[str] = None
) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    if source_id:
        try:
            source = database.sources.get(
                db, source_id, with_state=True, user_id=user_id
            )
        except database.NotFound:
            return abort(404)

        if source.user_id != user_id:
            return abort(404)

    elif kind:
        source = model.Source(kind=kind, user_id=user_id, name="", group_id=0)
    else:
        return abort(400)

    src = sources.get_source(source, {})
    user_settings = database.settings.get_dict(db, source.user_id)
    source_form = forms.SourceForm.from_model(source)
    source_form.settings = [
        forms.Field.from_input_params(
            param, source.settings, "sett-", user_settings.get(param.name)
        )
        for param in src.params
    ]
    errors = {}
    user_id = session["user"]
    entity_hash = str(hash(source))

    if request.method == "POST":
        if entity_hash == request.form["_entity_hash"]:
            source_form.update_from_request(request.form)
            errors = source_form.validate()
            u_source = source_form.update_model(source)
            assert u_source.settings is not None
            errors.update(src.validate_conf(u_source.settings, user_settings))
            if not errors:
                next_action = request.form.get("next_action")
                if next_action == "save_activate":
                    u_source.status = model.SourceStatus.ACTIVE

                u_source = src.upgrade_conf(u_source)
                u_source = database.sources.save(db, u_source)

                # adjust next check time when interval changed
                if (
                    source_id
                    and source.interval != u_source.interval
                    and u_source.interval
                ):
                    interval = common.parse_interval(u_source.interval)
                    assert source.state
                    source.state.adjust_next_update(interval)
                    database.sources.save_state(db, source.state, user_id)

                db.commit()
                flash(gettext("Source saved"))
                if next_action == "edit_filters":
                    return redirect(
                        url_for("source.source_filters", source_id=u_source.id)
                    )

                return redirect(url_for("root.sources"))
        else:
            flash(gettext("Source changed somewhere else; reloading..."))

    return render_template(
        "source.html",
        groups=database.groups.get_all(db, user_id),
        form=source_form,
        errors=errors,
        source_cls=src,
        source=source,
        entity_hash=entity_hash,
    )


@BP.route("/<int:source_id>/entries")
@BP.route("/<int:source_id>/entries/<mode>")
@BP.route("/<int:source_id>/entries/<mode>/<int:page>")
def source_entries(
    source_id: int, mode: str = "unread", page: int = 0
) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    source = database.sources.get(
        db, source_id, with_group=True, user_id=user_id
    )
    if not source:
        return abort(404)

    offset = (page or 0) * c.PAGE_LIMIT
    mode = "all" if mode == "all" else "unread"
    unread = mode == "unread"

    entries = list(
        database.entries.find(
            db,
            user_id,
            source_id=source_id,
            unread=unread,
            limit=c.PAGE_LIMIT,
            offset=offset,
        )
    )

    total_entries = database.entries.get_total_count(
        db, user_id, unread=unread, source_id=source_id
    )

    data = c.preprate_entries_list(entries, page, total_entries, "update")

    return render_template(
        "source_entries.html", source=source, showed=mode, **data
    )


@BP.route("/<int:source_id>/mark/read", methods=["POST"])
def source_mark_read(source_id: int) -> ty.Any:
    """Mark all entries in source read."""
    db = c.get_db()
    min_id = int(request.args.get("min_id", -1))
    max_id = int(request.args["max_id"])
    user_id = session["user"]
    r_ids = request.args.get("ids")
    ids = list(map(int, r_ids.split(","))) if r_ids else None

    marked = database.sources.mark_read(
        db, user_id, source_id, max_id=max_id, min_id=min_id, ids=ids
    )
    db.commit()
    if request.args.get("go") == "next":
        n_source_id = database.sources.find_next_unread(db, user_id)
        if n_source_id:
            return {
                "url": url_for("source.source_entries", source_id=n_source_id),
                "marked": marked,
            }

    if min_id:
        dst = url_for(
            "source.source_entries",
            source_id=source_id,
            page=request.args.get("page"),
            mode=request.args.get("mode"),
        )
    else:
        dst = url_for("root.sources")

    return {"url": dst, "marked": marked}


@BP.route("/<int:source_id>/filters")
def source_filters(source_id: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    source = database.sources.get(db, source_id, user_id=user_id)
    if not source:
        return abort(404)

    _LOG.debug("source.filters: %s", source.filters)
    filter_fields = [
        forms.Filter(fltr["name"]) for fltr in source.filters or []
    ]
    return render_template(
        "source_filters.html", source=source, filters=filter_fields
    )


@BP.route("/<int:source_id>/filter/add")
def source_filter_add(source_id: int) -> ty.Any:
    filters_info = filters.filters_info()
    return render_template(
        "filter_new.html", source_id=source_id, filters_info=filters_info
    )


@BP.route("/<int:source_id>/filter/<idx>/edit", methods=["GET", "POST"])
def source_filter_edit(source_id: int, idx: ty.Union[int, str]) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    try:
        source = database.sources.get(db, source_id, user_id=user_id)
    except database.NotFound:
        return abort(404)

    is_new = idx == "new"
    if not is_new:
        sfidx = int(idx)
        is_new = sfidx < 0 or sfidx >= len(source.filters or [])

    if is_new:  # new filter
        name = request.args.get("name")
        if not name:
            return redirect(url_for("source_filter_add", source_id=source_id))

        conf = {"name": request.args["name"]}
        sfidx = -1
    else:
        conf = source.filters[sfidx]

    fltr = filters.get_filter(conf)
    if not fltr:
        _LOG.warning(
            "invalid filter for source %d [%d]: %r", source_id, sfidx, conf
        )
        return abort(400)

    # for new filters without parameters, save it
    if is_new and not fltr.params:
        return _save_filter(db, source_id, sfidx, conf)

    errors = {}
    form = forms.FieldsForm(
        [
            forms.Field.from_input_params(param, conf, prefix="sett-")
            for param in fltr.params
        ]
    )

    entity_hash = str(hash(source))

    if request.method == "POST":
        if entity_hash == request.form["_entity_hash"]:
            form.update_from_request(request.form)
            conf.update(form.values_map())
            errors = dict(fltr.validate_conf(conf))
            if not errors:
                return _save_filter(db, source_id, sfidx, conf)
        else:
            flash("Source changed somewhere else; reloading...")

    return render_template(
        "filter_edit.html",
        filter=conf,
        source=source,
        form=form,
        errors=errors,
        fltr=fltr,
        entity_hash=entity_hash,
    )


# def _build_filter_conf_from_req(
#     fltr: filters.AbstractFilter, conf: model.ConfDict
# ):
#     param_types = fltr.get_param_types()
#     for key, val in request.form.items():
#         if key.startswith("sett-"):
#             param_name = key[5:]
#             if val:
#                 param_type = param_types[param_name]
#                 conf[param_name] = param_type(val)
#             else:
#                 conf[param_name] = None

#     return conf


def _save_filter(
    db: database.DB, source_id: int, idx: int, conf: model.ConfDict
) -> ty.Any:
    database.sources.update_filter(db, source_id, idx, conf)
    db.commit()
    flash("Filter saved")
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/<int:source_id>/filter/<int:idx>/move/<move>")
def source_filter_move(source_id: int, idx: int, move: str) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    database.sources.move_filter(db, user_id, source_id, idx, move)
    db.commit()
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/<int:source_id>/filter/<int:idx>/delete")
def source_filter_delete(source_id: int, idx: int) -> ty.Any:
    db = c.get_db()
    user_id = session["user"]
    database.sources.delete_filter(db, user_id, source_id, idx)
    db.commit()
    return redirect(url_for("source.source_filters", source_id=source_id))


@BP.route("/source/<int:source_id>/entry/<mode>/<int:entry_id>")
def source_entry(source_id: int, mode: str, entry_id: int) -> ty.Any:
    """Display entry with marking as read."""
    db = c.get_db()
    user_id = session["user"]
    try:
        src = database.sources.get(db, source_id, user_id=user_id)
    except database.NotFound:
        return abort(404)

    entry = database.entries.get(
        db, entry_id, with_source=True, with_group=True
    )
    if user_id != entry.user_id or source_id != entry.source_id:
        return abort(404)

    if entry.read_mark == model.EntryReadMark.UNREAD:
        database.entries.mark_read(
            db,
            user_id,
            entry_id=entry_id,
            read=model.EntryReadMark.MANUAL_READ,
        )
        entry.read_mark = model.EntryReadMark.MANUAL_READ
        db.commit()

    unread = mode != "all"
    next_entry = database.sources.find_next_entry_id(
        db, source_id, entry.id, unread
    )
    prev_entry = database.sources.find_prev_entry_id(
        db, source_id, entry.id, unread
    )
    return render_template(
        "source_entry.html",
        entry=entry,
        source_id=source_id,
        next_entry=next_entry,
        prev_entry=prev_entry,
        mode=mode,
        source=src,
    )


@BP.route("/source/<int:source_id>/next_unread")
def source_next_unread(
    source_id: int,  # pylint: disable=unused-argument
) -> ty.Any:
    db = c.get_db()
    n_source_id = database.sources.find_next_unread(db, session["user"])
    if n_source_id:
        return redirect(
            url_for("source.source_entries", source_id=n_source_id)
        )

    flash(gettext("No more unread sources..."))
    return redirect(url_for("root.sources"))
