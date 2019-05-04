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


_GET_ALL_SQL = """
select s.key, coalesce(us.value, s.value) as value,
    s.value_type, s.description, us.user_id
from settings s
left join user_settings us on us.key = s.key and us.user_id=?
"""


def get_all(db, user_id: int) -> ty.Iterable[model.Setting]:
    """ Get all settings for given user. """
    assert user_id
    cur = db.cursor()
    for row in cur.execute(_GET_ALL_SQL, (user_id, )):
        yield _setting_from_row(row)


_GET_SQL = """
select s.key, coalesce(us.value, s.value) as value,
    s.value_type, s.description, us.user_id
from settings s
left join user_settings us on us.key = s.key and us.user_id=?
where s.key=?
"""


def get(db, key: str, user_id: int) -> ty.Optional[model.Setting]:
    """ Get one setting for given user """
    cur = db.cursor()
    cur.execute(_GET_SQL, (user_id, key))
    row = cur.fetchone()
    return _setting_from_row(row) if row else None


def save_all(db, settings: ty.List[model.Setting]):
    """ Save all settings """
    cur = db.cursor()
    rows = [(setting.key, json.dumps(setting.value), setting.user_id)
            for setting in settings]
    cur.executemany(
        "delete from user_settings where key=? and user_id=?",
        [(setting.key, setting.user_id) for setting in settings])
    cur.executemany("insert into user_settings (key, value, user_id) "
                    "values (?, ?, ?)", rows)
    db.commit()


def get_value(db, key: str, user_id: int, default=None) \
        -> ty.Any:
    """ Get value of setting for given user """
    setting = get(db, key, user_id)
    return setting.value if setting else default


def get_dict(db, user_id: int) -> ty.Dict[str, ty.Any]:
    """ Get dictionary of setting for given user. """
    return {setting.key: setting.value
            for setting in get_all(db, user_id)}


def _setting_from_row(row) -> model.Setting:
    value = row['value']
    if value and isinstance(value, str):
        value = json.loads(value)
    return model.Setting(row['key'], value, row['value_type'],
                         row['description'], row['user_id'])
