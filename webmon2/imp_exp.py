#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Import/Export sources & groups.
"""

import json
import logging

from webmon2 import database, model

_LOG = logging.getLogger(__name__)


def dump_object(obj, attrs=None) -> dict:
    if not attrs:
        attrs = getattr(obj, "__slots__")
    return {attr: getattr(obj, attr) for attr in attrs}


def _dump_groups(groups):
    for group in groups:
        yield dump_object(group, ("id", "name", "user_id"))


def _dump_sources(sources):
    for source in sources:
        yield dump_object(
            source,
            (
                "id",
                "group_id",
                "kind",
                "name",
                "interval",
                "settings",
                "filters",
                "user_id",
                "status",
            ),
        )


def dump_export(db, user_id: int) -> str:
    data = {
        "groups": list(_dump_groups(database.groups.get_all(db, user_id))),
        "settings": list(
            map(dump_object, database.settings.get_all(db, user_id))
        ),
        "sources": list(_dump_sources(database.sources.get_all(db, user_id))),
    }
    return json.dumps(data)


def fill_object(obj, data: dict, attrs=None):
    if not attrs:
        attrs = getattr(obj, "__slots__")
    for attr in attrs:
        if attr in data and attr != "id":
            setattr(obj, attr, data[attr])


def dump_import(db, user_id: int, data_str: str):
    data = json.loads(data_str)
    if not data:
        raise RuntimeError("no data")

    groups_map = {}
    for group in data.get("groups") or []:
        grp = database.groups.find(db, user_id, group["name"])
        if not grp:
            grp = model.SourceGroup()
            fill_object(grp, group)
            grp.user_id = user_id
            grp = database.groups.save(db, grp)
        groups_map[group["id"]] = grp.id

    sources_map = {}
    for source in data.get("sources") or []:
        src = model.Source()
        fill_object(
            src,
            source,
            (
                "group_id",
                "kind",
                "name",
                "interval",
                "settings",
                "filters",
                "user_id",
                "status",
            ),
        )
        src.user_id = user_id
        src.group_id = groups_map[source["group_id"]]
        src = database.sources.save(db, src)
        sources_map[source["id"]] = src.id
