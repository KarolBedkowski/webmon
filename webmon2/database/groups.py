#!/usr/bin/python3
"""

Copyright (c) Karol Będkowski, 2016-2022

This file is part of webmon.
Licence: GPLv2+
"""
import hashlib
import logging
import random
import typing as ty
from datetime import datetime

from webmon2 import common, model

from . import _dbcommon as dbc
from ._db import DB

_LOG = logging.getLogger(__name__)


def get_names(db: DB, user_id: int) -> list[tuple[int, str]]:
    """
    Get list of id, name all user groups ordered by name.
    """
    if not user_id:
        raise ValueError("missing user_id")

    with db.cursor() as cur:
        cur.execute(
            "SELECT id, name FROM source_groups "
            "WHERE user_id=%s ORDER BY name",
            (user_id,),
        )

        return cur.fetchall()  # type: ignore


_GET_SOURCE_GROUPS_SQL = """
SELECT sg.id, sg.name, sg.user_id, sg.feed, sg.mail_report,
    (
        SELECT count(1)
        FROM entries e
        JOIN sources s ON e.source_id = s.id
        WHERE e.read_mark = %(read_mark)s AND s.group_id = sg.id
    ) AS unread,
    (
        SELECT count(1) FROM sources s WHERE s.group_id = sg.id
    ) AS sources_count
FROM source_groups sg
WHERE sg.user_id = %(user_id)s
ORDER BY sg.name
"""


def get_all(db: DB, user_id: int) -> list[model.SourceGroup]:
    """Get all groups for `user_id` with number of unread entries"""
    if not user_id:
        raise ValueError("missing user_id")

    with db.cursor() as cur:
        cur.execute(
            _GET_SOURCE_GROUPS_SQL,
            {"user_id": user_id, "read_mark": model.EntryReadMark.UNREAD},
        )
        groups = [
            model.SourceGroup(
                id=id,
                name=name,
                user_id=user_id,
                feed=feed,
                unread=unread,
                sources_count=srcs_count,
                mail_report=mail_report,
            )
            for id, name, user_id, feed, mail_report, unread, srcs_count in cur
        ]

        return groups


_GET_SQL = """
SELECT id AS source_group__id,
    name AS source_group__name,
    user_id AS source_group__user_id,
    feed AS source_group__feed,
    mail_report AS source_group__mail_report
FROM source_groups
WHERE id=%s AND user_id=%s
"""


def get(db: DB, group_id: int, user_id: int) -> model.SourceGroup:
    """Get one group by `group_id`. Optionally check is group belong
    to `user_id`.

    Raises:
        `NotFound`: group not found
    """
    with db.cursor() as cur:
        cur.execute(_GET_SQL, (group_id, user_id))
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()

    return model.SourceGroup.from_row(row)


_FIND_SQL = """
SELECT id AS source_group__id,
    name AS source_group__name,
    user_id AS source_group__user_id,
    feed AS source_group__feed,
    mail_report AS source_group__mail_report
FROM source_groups
WHERE name=%s AND user_id=%s
"""


def find(db: DB, user_id: int, name: str) -> model.SourceGroup:
    """Get group by `name` for `user_id`.

    Raises:
        `NotFound`: group not found
    """
    with db.cursor() as cur:
        cur.execute(_FIND_SQL, (name, user_id))
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()

        return model.SourceGroup.from_row(row)


_GET_BY_FEED_SQL = """
SELECT id AS source_group__id,
    name AS source_group__name,
    user_id AS source_group__user_id,
    feed AS source_group__feed,
    mail_report AS source_group__mail_report
FROM source_groups
WHERE feed= %s
"""


def get_by_feed(db: DB, feed: str) -> model.SourceGroup:
    """Get group by `feed` id.

    Raises:
        `NotFound`: group not found
    """
    if feed == "off":
        raise dbc.NotFound()

    with db.cursor() as cur:
        cur.execute(_GET_BY_FEED_SQL, (feed,))
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()

        return model.SourceGroup.from_row(row)


def get_last_update(db: DB, group_id: int) -> ty.Optional[datetime]:
    """Find last update time for entries in group"""
    with db.cursor() as cur:
        cur.execute(
            "SELECT max(datetime(coalesce(updated, created))) "
            "FROM entries "
            "WHERE source_id IN (SELECT id FROM sources WHERE group_id= %s)",
            (group_id,),
        )
        row = cur.fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None


_INSERT_GROUP_SQL = """
INSERT INTO source_groups (name, user_id, feed, mail_report)
VALUES (
    %(source_group__name)s, %(source_group__user_id)s,
    %(source_group__feed)s, %(source_group__mail_report)s
)
RETURNING id
"""

_UPDATE_GROUP_SQL = """
UPDATE source_groups
SET name=%(source_group__name)s, feed=%(source_group__feed)s,
    mail_report=%(source_group__mail_report)s
WHERE id=%(source_group__id)s
"""


def save(db: DB, group: model.SourceGroup) -> model.SourceGroup:
    """Save / update group.
    Generate random group.feed if empty.
    User id is not updated.

    Return:
        updated group object
    """
    _LOG.debug("save: %r", group)

    if not group.feed:
        group.feed = _generate_group_feed(db)

    row = group.to_row()

    with db.cursor() as cur:
        if group.id is None:
            cur.execute(_INSERT_GROUP_SQL, row)
            group.id = cur.fetchone()[0]  # type: ignore
        else:
            cur.execute(_UPDATE_GROUP_SQL, row)

    return group


def _generate_group_feed(db: DB) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    with db.cursor() as cur:
        while True:
            feed = "".join(
                random.SystemRandom().choice(chars) for _ in range(32)
            )
            # check for duplicates
            cur.execute("select 1 from source_groups where feed= %s", (feed,))
            if not cur.fetchone():
                return feed


_GET_NEXT_UNREAD_GROUP_SQL = """
SELECT group_id
FROM sources s
JOIN entries e ON e.source_id = s.id
WHERE e.read_mark = %s AND s.user_id = %s
ORDER BY e.id
LIMIT 1
"""


def get_next_unread_group(db: DB, user_id: int) -> ty.Optional[int]:
    """Find group with unread entries for `user_id`.

    Return:
        group id or None if not Found
    """
    with db.cursor() as cur:
        cur.execute(
            _GET_NEXT_UNREAD_GROUP_SQL, (model.EntryReadMark.UNREAD, user_id)
        )
        row = cur.fetchone()
        return row[0] if row else None


_MARK_READ_SQL = """
UPDATE entries
SET read_mark=%(read_mark)s
WHERE source_id IN (SELECT id FROM sources WHERE group_id=%(group_id)s)
    AND (id<=%(max_id)s OR %(max_id)s<0) AND id>=%(min_id)s
    AND read_mark=%(unread)s AND user_id=%(user_id)s
"""
_MARK_READ_BY_IDS_SQL = """
UPDATE entries
SET read_mark=%(read_mark)s
WHERE id=ANY(%(ids)s) AND read_mark=%(unread)s AND user_id=%(user_id)s
"""


# pylint: disable=too-many-arguments
def mark_read(
    db: DB,
    user_id: int,
    group_id: int,
    max_id: ty.Optional[int] = None,
    min_id: ty.Optional[int] = None,
    ids: ty.Optional[list[int]] = None,
) -> int:
    """Mark entries in given `group_id` read.
    If `ids` is given mark entries from this list; else if `max_id` is given
    - mark entries in range `min_id` to `max_id` including.

    `ids` or (`max_id` and `min_id`) is required.

    Args:
        db: database obj
        group_id: group id (required)
        min_id, max_id: entries id range
        ids: list of entries id to set
    Return:
        number of changed entries
    """
    if not group_id:
        raise ValueError("missing group_id")

    if not ((min_id and max_id) or ids):
        raise ValueError("missing min/max id or ids")

    args = {
        "group_id": group_id,
        "min_id": min_id,
        "max_id": max_id,
        "user_id": user_id,
        "ids": ids,
        "read_mark": model.EntryReadMark.READ,
        "unread": model.EntryReadMark.UNREAD,
    }
    with db.cursor() as cur:
        if ids:
            cur.execute(_MARK_READ_BY_IDS_SQL, args)
        else:
            cur.execute(_MARK_READ_SQL, args)

        return cur.rowcount


def update_state(db: DB, group_id: int, last_modified: datetime) -> str:
    """Save (update or insert) group last modified information.

    Return:
        etag value
    """
    etag_h = hashlib.md5(str(group_id).encode("ascii"))
    etag_h.update(str(last_modified).encode("ascii"))
    etag = etag_h.hexdigest()

    with db.cursor() as cur:
        cur.execute(
            "SELECT last_modified, etag FROM source_group_state "
            "WHERE group_id=%s",
            (group_id,),
        )
        row = cur.fetchone()

    with db.cursor() as cur:
        if row:
            if row[0] > last_modified:
                return row[1]  # type: ignore

            cur.execute(
                "UPDATE source_group_state "
                "SET last_modified= %s, etag=%s "
                "WHERE group_id= %s",
                (last_modified, etag, group_id),
            )
        else:
            cur.execute(
                "insert into source_group_state (group_id, last_modified, "
                "etag)"
                "VALUES (%s, %s, %s)",
                (group_id, last_modified, etag),
            )

        return etag


def get_state(db: DB, group_id: int) -> ty.Optional[tuple[datetime, str]]:
    """Get group entries last modified information.

    Return:
        (last modified date, etag)
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT last_modified, etag FROM source_group_state "
            "WHERE group_id= %s",
            (group_id,),
        )
        row = cur.fetchone()

    if not row:
        last_updated = get_last_update(db, group_id)
        if not last_updated:
            return None

        etag = update_state(db, group_id, last_updated)
        return (last_updated, etag)

    return row[0], row[1]


def delete(db: DB, user_id: int, group_id: int) -> None:
    """Delete group; move existing sources to main (or first) group."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(1) FROM source_groups WHERE user_id=%s", (user_id,)
        )
        if not cur.fetchone()[0]:  # type: ignore
            raise common.OperationError("can't delete last group")

    with db.cursor() as cur:
        cur.execute(
            "SELECT count(1) FROM sources WHERE group_id=%s", (group_id,)
        )
        if cur.fetchone()[0]:  # type: ignore
            # there are sources in group find destination group
            dst_group_id = _find_dst_group(db, user_id, group_id)
            cur.execute(
                "UPDATE sources set group_id= %s WHERE group_id=%s",
                (dst_group_id, group_id),
            )
            _LOG.debug("moved %d sources", cur.rowcount)

    with db.cursor() as cur:
        cur.execute("DELETE FROM source_groups WHERE id= %s", (group_id,))


def _find_dst_group(db: DB, user_id: int, group_id: int) -> int:
    """Find group to move sources.

    Args:
        user_id: user id
        group_id: source group id

    Raises:
        `OperationError`: can't find appropriate group

    Return:
        destination group id
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM source_groups WHERE user_id= %s AND name='main' "
            "AND id != %s ORDER BY id LIMIT 1",
            (user_id, group_id),
        )
        row = cur.fetchone()

    if row:
        return row[0]  # type: ignore

    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM source_groups WHERE user_id= %s "
            "AND id != %s ORDER BY id LIMIT 1",
            (user_id, group_id),
        )
        row = cur.fetchone()

    if row:
        return row[0]  # type: ignore

    raise common.OperationError("can't find destination group for sources")


def find_next_entry_id(
    db: DB, group_id: int, entry_id: int, unread: bool = True
) -> ty.Optional[int]:
    """Find next entry to given in group.

    Args:
        db: database object
        group_id: user id (required)
        entry_id: current entry id
        unread: look only for unread entries
    Return:
        next entry id if exists or None

    FIXME:
        user_id, order_id ?
    """
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "SELECT min(e.id) "
                "FROM entries e JOIN sources s ON s.id = e.source_id "
                "WHERE e.id > %s AND e.read_mark=%s AND s.group_id=%s",
                (entry_id, model.EntryReadMark.UNREAD, group_id),
            )
        else:
            cur.execute(
                "SELECT min(e.id) "
                "FROM entries e JOIN sources s ON s.id = e.source_id "
                "WHERE e.id > %s AND s.group_id=%s",
                (entry_id, group_id),
            )

        row = cur.fetchone()
        return row[0] if row else None


def find_prev_entry_id(
    db: DB, group_id: int, entry_id: int, unread: bool = True
) -> ty.Optional[int]:
    """Find previous entry to given in group.

    Args:
        db: database object
        group_id: user id (required)
        entry_id: current entry id
        unread: look only for unread entries
    Return:
        previous entry id if exists or None

    FIXME:
        user_id, order_id ?
    """
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "SELECT max(e.id) "
                "FROM entries e JOIN sources s ON s.id = e.source_id "
                "WHERE e.id < %s AND e.read_mark=%s AND s.group_id=%s",
                (entry_id, model.EntryReadMark.UNREAD, group_id),
            )
        else:
            cur.execute(
                "SELECT max(e.id) "
                "FROM entries e JOIN sources s ON s.id = e.source_id "
                "WHERE e.id < %s AND s.group_id=%s",
                (entry_id, group_id),
            )

        row = cur.fetchone()
        return row[0] if row else None
