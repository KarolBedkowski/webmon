#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2019
#
# Distributed under terms of the GPLv3 license.

"""
Access to settings in db
"""

import logging
import typing as ty

import json

from webmon2 import model

_LOG = logging.getLogger(__file__)


def get_all(db, user_id) -> ty.Iterable[model.Setting]:
    cur = db.cursor()
    if user_id is None:
        cur.execute(
            "select key, value, value_type, description from settings")
    else:
        cur.execute(
            "select s.key, coalesce(us.value, s.value) as value, "
            "s.value_type, s.description, us.user_id "
            "from settings s left join user_settings us on us.key = s.key "
            "where us.user_id=? or us.user_id is null", (user_id, ))
    for row in cur:
        yield _setting_from_row(row)


def get(db, key: str, user_id: int) -> ty.Optional[model.Setting]:
    cur = db.cursor()
    cur.execute(
        "select s.key, coalesce(us.value, s.value) as value, "
        "s.value_type, s.description, us.user_id "
        "from settings s left join user_settings us on us.key = s.key "
        "where us.user_id=? and s.key=?", (user_id, key))
    row = cur.fetchone()
    return _setting_from_row(row) if row else None


def save(db, setting: model.Setting):
    cur = db.cursor()
    cur.execute("delete from user_settings where key=? and user_id=?",
                (setting.key, setting.user_id))
    cur.execute("insert into user_settings (key, value, user_id) "
                "values (?, ?, ?)",
                (setting.key, json.dumps(setting.value), setting.user_id))
    db.commit()


def save_all(db, settings: ty.List[model.Setting]):
    cur = db.cursor()
    rows = [(setting.key, json.dumps(setting.value), setting.user_id)
            for setting in settings]
    _LOG.debug("rows: %r", rows)
    cur.executemany(
        "delete from user_settings where key=? and user_id=?",
        [(setting.key, setting.user_id) for setting in settings])
    cur.executemany("insert into user_settings (key, value, user_id) "
                    "values (?, ?, ?)", rows)
    db.commit()


def get_value(db, key: str, user_id: int, default=None) \
        -> ty.Any:
    setting = get(db, key, user_id)
    return setting.value if setting else default


def get_map(db, user_id: int) -> ty.Dict[str, ty.Any]:
    return {setting.key: setting.value
            for setting in get_all(db, user_id)}


def _setting_from_row(row) -> model.Setting:
    value = row['value']
    if value and isinstance(value, str):
        value = json.loads(value)
    return model.Setting(row['key'], value, row['value_type'],
                         row['description'], row['user_id'])
