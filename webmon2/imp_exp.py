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
import typing as ty

from webmon2 import database, model

_LOG = logging.getLogger(__name__)


def dump_object(
    obj: ty.Any, attrs: ty.Optional[ty.Iterable[str]] = None
) -> ty.Dict[str, ty.Any]:
    if not attrs and hasattr(obj, "__slots__"):
        attrs = getattr(obj, "__slots__")

    if not attrs and hasattr(obj, "__dataclass_fields__"):
        attrs = getattr(obj, "__dataclass_fields__")

    if not attrs:
        return {}

    return {attr: getattr(obj, attr) for attr in attrs}


def _dump_groups(
    groups: ty.Iterable[model.SourceGroup],
) -> ty.Iterable[ty.Dict[str, ty.Any]]:
    for group in groups:
        yield dump_object(group, ("id", "name", "user_id"))


def _dump_sources(
    sources: ty.Iterable[model.Source],
) -> ty.Iterable[ty.Dict[str, ty.Any]]:
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


def dump_export(db: database.DB, user_id: int) -> str:
    data = {
        "groups": list(_dump_groups(database.groups.get_all(db, user_id))),
        "settings": list(
            map(dump_object, database.settings.get_all(db, user_id))
        ),
        "sources": list(_dump_sources(database.sources.get_all(db, user_id))),
    }
    return json.dumps(data)


def fill_object(
    obj: ty.Any,
    data: ty.Dict[str, ty.Any],
    attrs: ty.Optional[ty.Iterable[str]] = None,
) -> None:
    if not attrs:
        attrs = getattr(obj, "__slots__")

    if not attrs:
        return

    for attr in attrs:
        if attr in data and attr != "id":
            setattr(obj, attr, data[attr])


def dump_import(db: database.DB, user_id: int, data_str: str) -> None:
    data = json.loads(data_str)
    if not data:
        raise RuntimeError("no data")

    groups_map: ty.Dict[int, int] = {}
    for group in data.get("groups") or []:
        grp = database.groups.find(db, user_id, group["name"])
        if not grp:
            grp = model.SourceGroup(
                user_id=user_id,
                name=group["name"],
                feed=group.get("feed"),
                mail_report=group.get("mail_report"),
            )
            grp = database.groups.save(db, grp)

        assert grp.id
        groups_map[group["id"]] = grp.id

    sources_map = {}
    for source in data.get("sources") or []:
        src = model.Source(
            user_id=user_id,
            group_id=groups_map[source["group_id"]],
            name=source["name"],
            kind=source["kind"],
        )
        src.status = model.SourceStatus(source["status"])
        fill_object(
            src,
            source,
            (
                "group_id",
                "interval",
                "settings",
                "filters",
                "user_id",
            ),
        )
        src = database.sources.save(db, src)
        sources_map[source["id"]] = src.id
