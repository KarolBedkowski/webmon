#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Access to entries in db.
"""
import logging
import typing as ty
from datetime import date, datetime

from webmon2 import model

from . import _dbcommon as dbc
from . import binaries, sources
from ._db import DB
from ._dbcommon import tyCursor

_ = ty
_LOG = logging.getLogger(__name__)


_GET_ENTRIES_SQL_MAIN = """
SELECT
    e.id AS entry__id,
    e.source_id AS entry__source_id,
    e.updated AS entry__updated,
    e.created AS entry__created,
    e.read_mark AS entry__read_mark,
    e.star_mark AS entry__star_mark,
    e.status AS entry__status,
    e.oid AS entry__oid,
    e.title AS entry__title,
    e.url AS entry__url,
    e.opts AS entry__opts,
    e.content AS entry__content,
    e.user_id AS entry__user_id,
    e.icon AS entry__icon,
    e.score AS entry__score
FROM entries e
"""

_GET_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE e.user_id = %(user_id)s
"""
)

_GET_UNREAD_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE read_mark = %(unread)s AND e.user_id=%(user_id)s
"""
)

_GET_UNREAD_ENTRIES_BY_SOURCE_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE read_mark = %(unread)s
    AND e.source_id=%(source_id)s
    AND e.user_id=%(user_id)s
"""
)

_GET_ENTRIES_BY_SOURCE_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE e.source_id = %(source_id)s AND e.user_id=%(user_id)s
"""
)

_GET_UNREAD_ENTRIES_BY_GROUP_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
JOIN sources s ON s.id = e.source_id
WHERE read_mark = %(unread)s
    AND s.group_id = %(group_id)s
    AND e.user_id = %(user_id)s
"""
)

_GET_ENTRIES_BY_GROUP_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
JOIN sources s ON s.id = e.source_id
WHERE s.group_id = %(group_id)s
    AND e.user_id=%(user_id)s
"""
)

_GET_STARRED_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE e.star_mark = 1 AND e.user_id=%(user_id)s
"""
)

_GET_ENTRIES_BY_GROUP_FEED_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
JOIN sources s ON s.id = e.source_id
WHERE s.group_id = %(group_id)s
ORDER BY e.id DESC
LIMIT 100
"""
)

_GET_HISTORY_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE e.read_mark = %(read)s AND e.user_id=%(user_id)s
ORDER BY e.id
"""
)

_GET_ENTRIES_FULLTEXT_TITLE_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE to_tsvector(title) @@ to_tsquery('pg_catalog.simple', %(query)s)
    AND e.user_id=%(user_id)s
"""
)

_GET_ENTRIES_FULLTEXT_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
WHERE to_tsvector(content || ' ' || title)
        @@ to_tsquery('pg_catalog.simple', %(query)s)
    AND e.user_id=%(user_id)s
"""
)


def _get_find_sql(
    source_id: ty.Optional[int], group_id: ty.Optional[int], unread: bool
) -> str:
    if source_id:
        if unread:
            return _GET_UNREAD_ENTRIES_BY_SOURCE_SQL
        return _GET_ENTRIES_BY_SOURCE_SQL

    if group_id:
        if unread:
            return _GET_UNREAD_ENTRIES_BY_GROUP_SQL
        return _GET_ENTRIES_BY_GROUP_SQL

    if unread:
        return _GET_UNREAD_ENTRIES_SQL

    return _GET_ENTRIES_SQL


def _yield_entries(
    cur: tyCursor, user_sources: model.UserSources
) -> model.Entries:
    for row in cur:
        entry = model.Entry.from_row(row)
        entry.source = user_sources.get(entry.source_id)
        yield entry


def get_starred(db: DB, user_id: int) -> model.Entries:
    """Get all starred entries for given user"""
    if not user_id:
        raise ValueError("missing user_id")

    user_sources = sources.get_all_dict(db, user_id)

    with db.cursor() as cur:
        cur.execute(_GET_STARRED_ENTRIES_SQL, {"user_id": user_id})
        yield from _yield_entries(cur, user_sources)


def get_history(db: DB, user_id: int) -> model.Entries:
    """Get all entries manually read (read_mark=2) for given user"""
    if not user_id:
        raise ValueError("missing user_id")

    user_sources = sources.get_all_dict(db, user_id)

    with db.cursor() as cur:
        cur.execute(
            _GET_HISTORY_ENTRIES_SQL,
            {"user_id": user_id, "read": model.EntryReadMark.MANUAL_READ},
        )
        yield from _yield_entries(cur, user_sources)


def get_total_count(
    db: DB,
    user_id: int,
    source_id: ty.Optional[int] = None,
    group_id: ty.Optional[int] = None,
    unread: bool = True,
) -> int:
    """Get number of read/all entries for user/source/group.

    Args:
        db: database object
        user_id: user_id
        source_id: optional source id to filter entries
        group_id: optional sources group id to filter entries
        unread: count only unread entries or all
    Returns:
        number of entries
    """
    if not user_id and not source_id and not group_id:
        raise ValueError("missing user_id/source_id/group_id")

    args = {
        "group_id": group_id,
        "source_id": source_id,
        "user_id": user_id,
        "unread": model.EntryReadMark.UNREAD,
    }

    if source_id:
        sql = "SELECT count(1) FROM entries WHERE source_id=%(source_id)s "
    elif group_id:
        sql = (
            "SELECT count(1) FROM entries e "
            "JOIN sources s ON e.source_id = s.id "
            "WHERE s.group_id=%(group_id)s "
        )
    else:
        sql = "SELECT count(1) FROM entries WHERE user_id=%(user_id)s"

    if unread:
        sql += " AND read_mark=%(unread)s"

    _LOG.debug("get_total_count(%r): %s", args, sql)

    with db.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()[0]  # type: ignore


_ORDER_SQL = {
    "update": " order by e.updated",
    "update_desc": " order by e.updated desc",
    "title": " order by e.title",
    "title_desc": " order by e.title desc",
    "score": " order by e.score",
    "score_desc": " order by e.score desc",
}


def _get_order_sql(order: ty.Optional[str]) -> str:
    """Get sql part for order entries."""
    if not order:
        return " order by e.updated"

    return _ORDER_SQL.get(order, " order by e.updated")


# pylint: disable=too-many-arguments,too-many-locals
def find(
    db: DB,
    user_id: int,
    source_id: ty.Optional[int] = None,
    group_id: ty.Optional[int] = None,
    unread: bool = True,
    offset: ty.Optional[int] = None,
    limit: ty.Optional[int] = None,
    order: ty.Optional[str] = None,
) -> model.Entries:
    """Find entries for user/source/group unread or all.
    Limit and offset work only for getting all entries.

    Args:
        db: database object
        user_id: user id
        source_id: optional source to filter entries
        group_id: optional sources group id to filter entries
        unread: get only unread entries
        offset: get entries from `offset` index
        limit: get only `limit` number of entries
        order: optional sorting
    """
    args = {
        "limit": limit or 25,
        "offset": offset or 0,
        "group_id": group_id,
        "source_id": source_id,
        "user_id": user_id,
        "unread": model.EntryReadMark.UNREAD,
    }
    sql = _get_find_sql(source_id, group_id, unread)
    sql += _get_order_sql(order)
    if limit:
        # for unread there is no pagination
        sql += " LIMIT %(limit)s OFFSET %(offset)s"

    _LOG.debug("find(%r): %s", args, sql)

    user_sources = sources.get_all_dict(db, user_id, group_id=group_id)

    with db.cursor() as cur:
        cur.execute(sql, args)
        yield from _yield_entries(cur, user_sources)


# pylint: disable=too-many-arguments,too-many-locals
def find_fulltext(
    db: DB,
    user_id: int,
    query: str,
    title_only: bool,
    group_id: ty.Optional[int] = None,
    source_id: ty.Optional[int] = None,
    order: ty.Optional[str] = None,
) -> model.Entries:
    """Find entries for user by full-text search on title or title and content.
    Search in source (if given source_id) or in group (if given group_id)
    or in all entries given user

    Args:
        db: database object
        user_id: user id
        query: expression to look for
        group_id: optional sources group id to filter entries
        source_id: optional source to filter entries
        order: optional sorting
    """
    args = {
        "user_id": user_id,
        "query": query,
        "group_id": group_id,
        "source_id": source_id,
    }
    sql = (
        _GET_ENTRIES_FULLTEXT_TITLE_SQL
        if title_only
        else _GET_ENTRIES_FULLTEXT_SQL
    )

    if source_id:
        sql += " AND e.source_id=%(source_id)s "
    elif group_id:
        sql += " AND s.group_id=%(group_id)s "
    else:
        sql += " AND e.user_id=%(user_id)s "

    sql += _get_order_sql(order)

    user_sources = sources.get_all_dict(db, user_id, group_id=group_id)

    with db.cursor() as cur:
        cur.execute(sql, args)
        yield from _yield_entries(cur, user_sources)


def find_for_feed(db: DB, user_id: int, group_id: int) -> model.Entries:
    """Find all entries by group feed."""
    user_sources = sources.get_all_dict(db, user_id, group_id=group_id)
    with db.cursor() as cur:
        cur.execute(_GET_ENTRIES_BY_GROUP_FEED_SQL, {"group_id": group_id})
        yield from _yield_entries(cur, user_sources)


_GET_ENTRY_SQL = """
SELECT
    id AS entry__id,
    source_id AS entry__source_id,
    updated AS entry__updated,
    created AS entry__created,
    read_mark AS entry__read_mark,
    star_mark AS entry__star_mark,
    status AS entry__status,
    oid AS entry__oid,
    title AS entry__title,
    url AS entry__url,
    opts AS entry__opts,
    content AS entry__content,
    user_id AS entry__user_id,
    icon AS entry__icon,
    score AS entry__score
FROM entries
"""


def get(
    db: DB,
    id_: ty.Optional[int] = None,
    oid: ty.Optional[str] = None,
    with_source: bool = False,
    with_group: bool = False,
) -> model.Entry:
    if not id_ and oid is None:
        raise ValueError("missing id/oid")

    with db.cursor() as cur:
        if id_ is not None:
            sql = _GET_ENTRY_SQL + "WHERE id=%(id)s"
        else:
            sql = _GET_ENTRY_SQL + "WHERE oid=%(oid)s"

        cur.execute(sql, {"oid": oid, "id": id_})
        row = cur.fetchone()

    if not row:
        raise dbc.NotFound()

    entry = model.Entry.from_row(row)
    if with_source:
        entry.source = sources.get(db, entry.source_id, with_group=with_group)

    return entry


_INSERT_ENTRY_SQL = """
INSERT INTO entries (source_id, updated, created,
    read_mark, star_mark, status, oid, title, url, opts, content, user_id,
    icon, score)
VALUES (%(entry__source_id)s, %(entry__updated)s, %(entry__created)s,
    %(entry__read_mark)s, %(entry__star_mark)s, %(entry__status)s,
    %(entry__oid)s, %(entry__title)s, %(entry__url)s,
    %(entry__opts)s, %(entry__content)s, %(entry__user_id)s,
    %(entry__icon)s, %(entry__score)s)
ON CONFLICT (oid) DO NOTHING
RETURNING id
"""

_UPDATE_ENTRY_SQL = """
UPDATE entries
SET source_id=%(entry__source_id)s,
    updated=%(entry__updated)s,
    created=%(entry__created)s,
    read_mark=%(entry__read_mark)s,
    star_mark=%(entry__star_mark)s,
    status=%(entry__status)s,
    oid=%(entry__oid)s,
    title=%(entry__title)s,
    url=%(entry__url)s,
    opts=%(entry__opts)s,
    content=%(entry__content)s,
    icon=%(entry__icon)s,
    score=%(entry__score)s
WHERE id=%(entry__id)s
"""


def save(db: DB, entry: model.Entry) -> model.Entry:
    """Insert or update entry"""
    row = entry.to_row()
    with db.cursor() as cur:
        if entry.id is None:
            cur.execute(_INSERT_ENTRY_SQL, row)
            entry.id = cur.fetchone()[0]
        else:
            cur.execute(_UPDATE_ENTRY_SQL, row)

    _save_entry_icon(db, (entry,))
    return entry


def save_many(db: DB, entries: model.Entries) -> None:
    """Insert entries; where entry with given oid already exists - is deleted
    and inserted again; star mark is preserved.
    """
    # filter updated entries; should be deleted & inserted
    oids_to_delete = [
        (entry.oid,)
        for entry in entries
        if entry.status == model.EntryStatus.UPDATED
    ]
    if oids_to_delete:
        # find stared entries
        with db.cursor() as cur:
            cur.execute(
                "SELECT oid FROM entries WHERE oid=%s AND star_mark=1",
                oids_to_delete,
            )
            marked_oids = {row[0] for row in cur}

        with db.cursor() as cur:
            cur.executemany("DELETE FROM entries WHERE oid=%s", oids_to_delete)
            _LOG.debug(
                "to del %d, deleted: %d", len(oids_to_delete), cur.rowcount
            )
            # set star mark for updated entries
            if marked_oids:
                for entry in entries:
                    if entry.oid in marked_oids:
                        entry.star_mark = True

    rows = map(model.Entry.to_row, entries)

    with db.cursor() as cur:
        cur.executemany(_INSERT_ENTRY_SQL, rows)

    _save_entry_icon(db, entries)


def _save_entry_icon(db: DB, entries: model.Entries) -> None:
    saved = set()
    for entry in entries:
        if not entry.icon or entry.icon in saved or not entry.icon_data:
            continue

        content_type, data = entry.icon_data
        binaries.save(db, entry.user_id, content_type, entry.icon, data)
        saved.add(entry.icon)


def delete_old(
    db: DB, user_id: int, max_datetime: datetime
) -> ty.Tuple[int, int]:
    """Delete old entries for given user"""
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM entries WHERE star_mark=0 AND read_mark=%s "
            "AND updated<%s AND user_id=%s",
            (model.EntryReadMark.UNREAD, max_datetime, user_id),
        )
        deleted_entries = cur.rowcount
        cur.execute(
            "DELETE FROM history_oids "
            "WHERE source_id IN (SELECT id FROM sources WHERE user_id=%s) "
            "AND created<%s",
            (user_id, max_datetime),
        )
        deleted_oids = cur.rowcount
        return (deleted_entries, deleted_oids)


def mark_star(db: DB, user_id: int, entry_id: int, star: bool = True) -> int:
    """Change star mark for given entry"""
    db_star = 1 if star else 0
    _LOG.info(
        "mark_star user_id=%d, entry_id=%r,star=%r", user_id, entry_id, db_star
    )
    with db.cursor() as cur:
        cur.execute(
            "UPDATE entries SET star_mark=%s WHERE id=%s AND star_mark=%s",
            (db_star, entry_id, 1 - db_star),
        )
        changed = cur.rowcount

    _LOG.debug("changed: %d", changed)
    return changed  # type: ignore


def check_oids(db: DB, oids: ty.List[str], source_id: int) -> ty.Set[str]:
    """Check is given oids already exists in history table.
    Insert new and its oids;
    """
    if not source_id:
        raise ValueError("missing source_id")

    with db.cursor() as cur:
        result = set()  # type: ty.Set[str]
        for idx in range(0, len(oids), 100):
            part_oids = tuple(oids[idx : idx + 100])
            cur.execute(
                "SELECT oid FROM history_oids "
                "WHERE source_id=%s AND oid IN %s",
                (source_id, part_oids),
            )
            result.update(row[0] for row in cur)

    new_oids = [oid for oid in oids if oid not in result]
    _LOG.debug(
        "check_oids: check=%r, found=%d new=%d",
        len(oids),
        len(result),
        len(new_oids),
    )
    with db.cursor() as cur:
        cur.executemany(
            "INSERT INTO history_oids(source_id, oid) VALUES (%s, %s)",
            [(source_id, oid) for oid in new_oids],
        )

    return set(new_oids)


# pylint: disable=too-many-arguments
def mark_read(
    db: DB,
    user_id: int,
    entry_id: ty.Optional[int] = None,
    min_id: ty.Optional[int] = None,
    max_id: ty.Optional[int] = None,
    read: model.EntryReadMark = model.EntryReadMark.READ,
    ids: ty.Optional[ty.List[int]] = None,
) -> int:
    """Change read mark for given entry.
    If `entry_id` is given - mark only this one entry; else if `ids` is given -
    mark entries from this list; else if `max_id` is given - mark entries in
    range `min_id` (or 0) to `max_id` including.

    One of: `entry_id`, `max_id`, `ids` is required

    Args:
        db: database obj
        user_id: user id (required)
        entry_id: optional entry id to mark
        min_id, max_id: optional entries id range
        read: status to set
        ids: list of entries id to set
    Return:
        number of changed entries
    """
    if not user_id:
        raise ValueError("missing user_id")
    if not (entry_id or max_id or ids):
        raise ValueError("missing entry_id/max_id/ids")

    _LOG.debug(
        "mark_read entry_id=%r, min_id=%r, max_id=%r, read=%r, user_id=%r",
        entry_id,
        min_id,
        max_id,
        read,
        user_id,
    )
    with db.cursor() as cur:
        if entry_id:
            cur.execute(
                "UPDATE entries SET read_mark=%s WHERE id=%s AND user_id=%s",
                (read.value, entry_id, user_id),
            )
        elif ids:
            cur.execute(
                "UPDATE entries SET read_mark=%s "
                "WHERE id=ANY(%s) AND user_id=%s",
                (read.value, ids, user_id),
            )
        elif max_id:
            cur.execute(
                "UPDATE entries SET read_mark=%s "
                "WHERE id<=%s AND id>=%s AND user_id=%s",
                (read.value, max_id, min_id or 0, user_id),
            )
        changed = cur.rowcount

    return changed  # type: ignore


def mark_all_read(
    db: DB, user_id: int, max_date: ty.Union[None, date, datetime] = None
) -> int:
    """Mark all entries for given user as read; optionally mark only entries
    older than `max_date`.

    Args:
        db: database object
        user_id: user id
        max_date: optional date or datetime to mark entries older than this date
    Return:
        number of updated items
    """
    with db.cursor() as cur:
        if max_date:
            cur.execute(
                "UPDATE entries SET read_mark=%s WHERE user_id=%s "
                "AND read_mark=%s AND updated<%s",
                (
                    model.EntryReadMark.READ,
                    user_id,
                    model.EntryReadMark.UNREAD,
                    max_date,
                ),
            )
        else:
            cur.execute(
                "UPDATE entries set read_mark=%s WHERE user_id=%s "
                "AND read_mark=%s",
                (
                    model.EntryReadMark.READ,
                    user_id,
                    model.EntryReadMark.UNREAD,
                ),
            )

        return cur.rowcount  # type: ignore


_GET_RELATED_RM_ENTRY_SQL = """
WITH DATA AS (
	SELECT e.id,
		lag(id) OVER (PARTITION BY (user_id, read_mark) ORDER BY {order}) AS prev,
		lead(id) OVER (PARTITION BY (user_id, read_mark) ORDER BY {order}) AS NEXT
	FROM entries e
	WHERE user_id = %(user_id)s AND read_mark = %(read_mark)s
	ORDER BY {order}
)
SELECT prev, next
FROM DATA
WHERE id=%(entry_id)s
"""

_GET_RELATED_ENTRY_SQL = """
WITH DATA AS (
	SELECT e.id,
		lag(id) OVER (PARTITION BY (user_id, read_mark) ORDER by {order}) AS prev,
		lead(id) OVER (PARTITION BY (user_id, read_mark) ORDER by {order}) AS NEXT
	FROM entries e
	WHERE user_id = %(user_id)s
	ORDER BY {order}
)
SELECT prev, next
FROM DATA
WHERE id=%(entry_id)s
"""


def _get_related_sql(unread: bool, order: ty.Optional[str]) -> str:
    order_key = "updated"
    if order in ("title", "updated", "score"):
        order_key = order
    elif order == "title_desc":
        order_key = "title desc"
    elif order == "updated_desc":
        order_key = "updated desc"
    elif order == "score_desc":
        order_key = "score desc"

    if unread:
        return _GET_RELATED_RM_ENTRY_SQL.format(order=order_key)
    return _GET_RELATED_ENTRY_SQL.format(order=order_key)


def find_next_entry_id(
    db: DB,
    user_id: int,
    entry_id: int,
    unread: bool = True,
    order: ty.Optional[str] = None,
) -> ty.Optional[int]:
    """Find next entry to given.

    Args:
        db: database object
        user_id: user id (required)
        entry_id: current entry id
        unread: look only for unread entries
        order: optional entries sorting
    Return:
        next entry id if exists or None
    """
    with db.cursor() as cur:
        args = {
            "entry_id": entry_id,
            "user_id": user_id,
            "read_mark": model.EntryReadMark.UNREAD,
        }

        sql = _get_related_sql(unread, order)
        _LOG.debug("find_next_entry_id(%r): %s", args, sql)
        cur.execute(sql, args)
        row = cur.fetchone()
        return row[1] if row else None


def find_prev_entry_id(
    db: DB,
    user_id: int,
    entry_id: int,
    unread: bool = True,
    order: ty.Optional[str] = None,
) -> ty.Optional[int]:
    """Find previous entry to given.

    Args:
        db: database object
        user_id: user id (required)
        entry_id: current entry id
        unread: look only for unread entries
        order: optional entries sorting
    Return:
        previous entry id if exists or None
    """
    with db.cursor() as cur:
        args = {
            "entry_id": entry_id,
            "user_id": user_id,
            "read_mark": model.EntryReadMark.UNREAD,
        }
        sql = _get_related_sql(unread, order)
        _LOG.debug("find_prev_entry_id(%r): %s", args, sql)
        cur.execute(sql, args)
        row = cur.fetchone()
        return row[0] if row else None
