# Copyright (c) Karol Będkowski, 2016-2023
#
# Distributed under terms of the GPLv3 license.

"""
Access to settings in db
"""
from __future__ import annotations

import logging
import typing as ty

from webmon2 import model

from ._db import DB

_LOG = logging.getLogger(__name__)


_GET_ALL_SQL = """
SELECT s.key AS setting__key,
    coalesce(us.value, s.value) AS setting__value,
    s.value_type AS setting__value_type,
    us.user_id AS setting__user_id
FROM settings s
LEFT JOIN user_settings us ON us.key = s.key AND us.user_id=%s
"""


def get_all(db: DB, user_id: int) -> list[model.Setting]:
    """Get all settings for given user."""
    if not user_id:
        raise ValueError("missing user_id")

    with db.cursor_obj_row(model.Setting.from_row) as cur:
        cur.execute(_GET_ALL_SQL, (user_id,))
        return list(cur)


_GET_SQL = """
SELECT s.key AS setting__key,
    coalesce(us.value, s.value) AS setting__value,
    s.value_type AS setting__value_type,
    us.user_id AS setting__user_id
FROM settings s
LEFT JOIN user_settings us ON us.key = s.key AND us.user_id=%s
WHERE s.key=%s
"""


def get(db: DB, key: str, user_id: int) -> model.Setting | None:
    """Get one setting for given user"""
    with db.cursor_obj_row(model.Setting.from_row) as cur:
        cur.execute(_GET_SQL, (user_id, key))
        return cur.fetchone()


_INSERT_SQL = """
INSERT INTO user_settings (key, value, user_id)
VALUES (%(setting__key)s, %(setting__value)s, %(setting__user_id)s)
"""


def save_all(db: DB, settings: ty.Iterable[model.Setting]) -> None:
    """Save all settings"""
    rows = [setting.to_row() for setting in settings]

    with db.cursor() as cur:
        cur.executemany(
            "DELETE FROM user_settings WHERE key=%s AND user_id=%s",
            [(setting.key, setting.user_id) for setting in settings],
        )
        cur.executemany(_INSERT_SQL, rows)


Value = ty.Any


def get_value(
    db: DB, key: str, user_id: int, default: Value | None = None
) -> Value:
    """Get value of setting for given user"""
    setting = get(db, key, user_id)
    return setting.value if setting else default


def get_dict(db: DB, user_id: int) -> dict[str, ty.Any]:
    """Get dictionary of all setting for given user.

    Args:
        db: database object
        user_id: user id

    Return:
        dict: setting key -> setting value -

    """
    return {setting.key: setting.value for setting in get_all(db, user_id)}


_GET_GLOBAL_SQL = """
SELECT s.key AS setting__key,
    s.value AS setting__value,
    s.value_type AS setting__value_type
FROM settings s
ORDER by s.key
"""


def get_global(db: DB) -> list[model.Setting]:
    """Get global settings."""
    with db.cursor_obj_row(model.Setting.from_row) as cur:
        cur.execute(_GET_GLOBAL_SQL)
        return list(cur)


def set_value(db: DB, user_id: int, key: str, value: Value) -> None:
    """Update one user setting."""

    sett = model.Setting(key, value, "", "", user_id)

    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM user_settings WHERE key=%s AND user_id=%s",
            (key, user_id),
        )
        cur.execute(_INSERT_SQL, sett.to_row())
