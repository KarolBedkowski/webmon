# Copyright (c) Karol Będkowski, 2021
#
# Distributed under terms of the GPLv3 license.

"""
Database routines to system related objects
"""
from __future__ import annotations

import logging
import typing as ty

from webmon2 import model

from ._db import DB

_LOG = logging.getLogger(__name__)


_GET_DB_TAB_SIZESSQL = """
SELECT relname AS "tables",
    pg_size_pretty(pg_total_relation_size (c.oid)) AS "size"
FROM pg_class c
LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE nspname NOT IN ('pg_catalog','information_schema')
AND c.relkind <> 'i'
AND nspname !~ '^pg_toast'
AND c.relowner=(SELECT usesysid FROM pg_user WHERE usename=current_user)
ORDER BY 1
"""


def get_sysinfo(db: DB) -> ty.Iterable[tuple[str, ty.Any]]:
    """Get system info."""

    with db.cursor() as cur:
        cur.execute("SELECT 'Total entries', count(*) FROM entries")
        yield from cur

    with db.cursor() as cur:
        cur.execute(
            "SELECT 'Entries with read_mark=' || read_mark, count(*) "
            "FROM entries GROUP BY read_mark"
        )
        yield from cur

    with db.cursor() as cur:
        cur.execute("SELECT 'Total sources', count(*) FROM sources")
        yield from cur

    with db.cursor() as cur:
        cur.execute(
            "SELECT 'Sources with status=' || status, count(*) "
            "FROM sources GROUP BY status"
        )
        yield from cur


def get_table_sizes(db: DB) -> ty.Iterable[tuple[str, ty.Any]]:
    with db.cursor() as cur:
        cur.execute(_GET_DB_TAB_SIZESSQL)
        yield from cur


_GET_SESSION_SQL = """
select id as session__id, expiry as session__expiry, data as session__data
from sessions
where id = %s
"""


def get_session(db: DB, session_id: int) -> model.Session | None:
    with db.cursor() as cur:
        cur.execute(_GET_SESSION_SQL, (session_id,))
        if row := cur.fetchone():
            return model.Session.from_row(row)

    return None


def delete_session(db: DB, session_id: int) -> None:
    with db.cursor() as cur:
        cur.execute("delete from sessions where id=%s", (session_id,))


_SAVE_SESSION_SQL = """
INSERT INTO sessions (id, expiry, data)
VALUES (%(session__id)s, %(session__expiry)s, %(session__data)s)
ON CONFLICT (id)
DO UPDATE
SET expiry=%(session__expiry)s,
    data=%(session__data)s
"""


def save_session(db: DB, session: model.Session) -> None:
    with db.cursor() as cur:
        cur.execute(_SAVE_SESSION_SQL, session.to_row())


def delete_expired_sessions(db: DB) -> int:
    with db.cursor() as cur:
        cur.execute("delete from sessions where expiry <= now()")
        return cur.rowcount


def ping(db: DB) -> bool:
    with db.cursor() as cur:
        cur.execute("select now()")
        return bool(cur.fetchone())

    return False
