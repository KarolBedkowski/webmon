#!/usr/bin/python3
"""

Copyright (c) Karol Będkowski, 2016-2021

This file is part of webmon.
Licence: GPLv2+
"""
import logging
import typing as ty

import psycopg2

_LOG = logging.getLogger(__name__)


def get(db, datahash: str, user_id: int) -> ty.Optional[ty.Tuple[str, str]]:
    if not datahash:
        return None

    with db.cursor() as cur:
        cur.execute(
            "select data, content_type from binaries "
            "where datahash=%s and user_id=%s",
            (datahash, user_id),
        )
        row = cur.fetchone()
        return row


def save(db, user_id: int, content_type: str, datahash: str, data) -> None:
    _LOG.debug(
        "save binary: %r, %r, %r, %s",
        user_id,
        content_type,
        datahash,
        type(data),
    )
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO binaries (datahash, user_id, data, content_type) "
            "VALUES (%s, %s, %s, %s) "
            "ON conflict (datahash, user_id) DO NOTHING",
            (datahash, user_id, psycopg2.Binary(data), content_type),
        )


_REMOVE_UNUSED_SQL = """
DELETE FROM binaries b
WHERE user_id = %(user_id)s
    AND NOT EXISTS (
        SELECT NULL FROM entries e
        WHERE e.user_id = %(user_id)s and e.icon = b.datahash
    )
    AND NOT EXISTS (
        SELECT NULL
        FROM source_state ss
        JOIN sources s on s.id = ss.source_id
        WHERE s.user_id = %(user_id)s and ss.icon = b.datahash
    )
"""

_CLEAN_ENTRIES_SQL = """
UPDATE entries e
SET icon=NULL
WHERE icon IS NOT NULL
    AND NOT EXISTS (
        SELECT NULL
        FROM binaries b
        WHERE b.datahash=e.icon and b.user_id=e.user_id
    )
"""

_CLEAN_SOURCE_STATE_SQL = """
UPDATE source_state ss
SET icon=NULL
WHERE icon IS NOT NULL
    AND NOT EXISTS (
        SELECT NULL
        FROM binaries b
        JOIN sources s on b.user_id = s.user_id
        WHERE b.datahash=ss.icon and ss.source_id = s.id
    )
"""


def remove_unused(db, user_id: int) -> int:
    with db.cursor() as cur:
        cur.execute(_REMOVE_UNUSED_SQL, {"user_id": user_id})
        return cur.rowcount


def clean_sources_entries(db) -> ty.Tuple[int, int]:
    with db.cursor() as cur:
        cur.execute(_CLEAN_SOURCE_STATE_SQL)
        states_num = cur.rowcount
        cur.execute(_CLEAN_ENTRIES_SQL)
        entries_num = cur.rowcount
        return (states_num, entries_num)
