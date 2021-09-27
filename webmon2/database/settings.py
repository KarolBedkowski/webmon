#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2021
#
# Distributed under terms of the GPLv3 license.

"""
Access to settings in db
"""

import logging
import typing as ty

from webmon2 import model

_LOG = logging.getLogger(__name__)


_GET_ALL_SQL = """
select s.key as setting__key,
    coalesce(us.value, s.value) as setting__value,
    s.value_type as setting__value_type,
    s.description as setting__description,
    us.user_id as setting__user_id
from settings s
left join user_settings us on us.key = s.key and us.user_id=%s
"""


def get_all(db, user_id: int) -> ty.Iterable[model.Setting]:
    """Get all settings for given user."""
    if not user_id:
        raise ValueError("missing user_id")

    cur = db.cursor()
    cur.execute(_GET_ALL_SQL, (user_id,))
    for row in cur:
        yield model.Setting.from_row(row)

    cur.close()


_GET_SQL = """
select s.key as setting__key,
    coalesce(us.value, s.value) as setting__value,
    s.value_type as setting__value_type,
    s.description as setting__description,
    us.user_id as setting__user_id
from settings s
left join user_settings us on us.key = s.key and us.user_id=%s
where s.key=%s
"""


def get(db, key: str, user_id: int) -> ty.Optional[model.Setting]:
    """Get one setting for given user"""
    cur = db.cursor()
    cur.execute(_GET_SQL, (user_id, key))
    row = cur.fetchone()
    cur.close()
    return model.Setting.from_row(row) if row else None


_INSERT_SQL = """
insert into user_settings (key, value, user_id)
values (%(setting__key)s, %(setting__value)s, %(setting__user_id)s)
"""


def save_all(db, settings: ty.List[model.Setting]) -> None:
    """Save all settings"""
    cur = db.cursor()
    rows = [setting.to_row() for setting in settings]
    cur.executemany(
        "delete from user_settings where key=%s and user_id=%s",
        [(setting.key, setting.user_id) for setting in settings],
    )
    cur.executemany(_INSERT_SQL, rows)
    cur.close()


def get_value(db, key: str, user_id: int, default=None) -> ty.Any:
    """Get value of setting for given user"""
    setting = get(db, key, user_id)
    return setting.value if setting else default


def get_dict(db, user_id: int) -> ty.Dict[str, ty.Any]:
    """Get dictionary of setting for given user."""
    return {setting.key: setting.value for setting in get_all(db, user_id)}
