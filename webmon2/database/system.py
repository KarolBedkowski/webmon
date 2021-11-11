#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2021
#
# Distributed under terms of the GPLv3 license.

"""
Database routines to system related objects
"""

import logging
import typing as ty

from ._db import DB

_LOG = logging.getLogger(__name__)


_GET_STATS_SQL = """
SELECT s.key AS setting__key,
    coalesce(us.value, s.value) AS setting__value,
    s.value_type AS setting__value_type,
    s.description AS setting__description,
    us.user_id AS setting__user_id
FROM settings s
LEFT JOIN user_settings us ON us.key = s.key AND us.user_id=%s
"""


_GET_DB_TAB_SIZESSQL = """
SELECT relname AS "tables", pg_size_pretty(pg_total_relation_size (c.oid)) AS "size"
FROM pg_class c
LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE nspname NOT IN ('pg_catalog','information_schema')
AND c.relkind <> 'i'
AND nspname !~ '^pg_toast'
AND c.relowner=(SELECT usesysid FROM pg_user WHERE usename=current_user)
ORDER BY 1
"""


def get_sysinfo(db: DB) -> ty.Iterable[ty.Tuple[str, ty.Any]]:
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


def get_table_sizes(db: DB) -> ty.Iterable[ty.Tuple[str, ty.Any]]:
    with db.cursor() as cur:
        cur.execute(_GET_DB_TAB_SIZESSQL)
        yield from cur
