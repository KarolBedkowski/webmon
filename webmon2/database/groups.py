#!/usr/bin/python3
"""

Copyright (c) Karol Będkowski, 2016-2021

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

_GET_SOURCE_GROUPS_SQL = """
select sg.id, sg.name, sg.user_id, sg.feed, sg.mail_report,
    (select count(1)
        from entries e
        join sources s on e.source_id = s.id
        where e.read_mark = %(read_mark)s and s.group_id = sg.id
    ) as unread,
    (select count(1) from sources s where s.group_id = sg.id)
        as sources_count
from source_groups sg
where sg.user_id= %(user_id)s
order by sg.name
"""


def get_all(db: DB, user_id: int) -> ty.List[model.SourceGroup]:
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
select id as source_group__id,
    name as source_group__name,
    user_id as source_group__user_id,
    feed as source_group__feed,
    mail_report as source_group__mail_report
from source_groups
where id=%s and user_id=%s
"""


def get(
    db: DB, group_id: int, user_id: ty.Optional[int] = None
) -> model.SourceGroup:
    """Get one group by `group_id`. Optionally check is group belong to `user_id`.

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
select id as source_group__id,
    name as source_group__name,
    user_id as source_group__user_id,
    feed as source_group__feed,
    mail_report as source_group__mail_report
from source_groups
where name=%s and user_id=%s
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
select id as source_group__id,
    name as source_group__name,
    user_id as source_group__user_id,
    feed as source_group__feed,
    mail_report as source_group__mail_report
from source_groups
where feed= %s
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
            "select max(datetime(coalesce(updated, created))) from entries "
            "where source_id in (select id from sources where group_id= %s)",
            (group_id,),
        )
        row = cur.fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None


_INSERT_GROUP_SQL = """
insert into source_groups (name, user_id, feed, mail_report)
values (
    %(source_group__name)s, %(source_group__user_id)s,
    %(source_group__feed)s, %(source_group__mail_report)s
)
returning id
"""

_UPDATE_GROUP_SQL = """
update source_groups
set name=%(source_group__name)s, feed=%(source_group__feed)s,
    mail_report=%(source_group__mail_report)s
where id=%(source_group__user_id)s
"""


def save(db: DB, group: model.SourceGroup) -> model.SourceGroup:
    """Save / update group.
    Generate random group.feed if empty.

    Return:
        updated group object
    """
    if not group.feed:
        group.feed = _generate_group_feed(db)

    row = group.to_row()

    with db.cursor() as cur:
        if group.id is None:
            cur.execute(_INSERT_GROUP_SQL, row)
            group.id = cur.fetchone()[0]
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
WHERE e.read_mark = %s
    AND s.user_id = %s
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
update entries
set read_mark=%(read_mark)s
where source_id in (select id from sources where group_id=%(group_id)s)
    and (id<=%(max_id)s or %(max_id)s<0) and id>=%(min_id)s
    and read_mark=%(unread)s and user_id=%(user_id)s
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
    ids: ty.Optional[ty.List[int]] = None,
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

        return cur.rowcount  # type: ignore


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
            "select last_modified, etag from source_group_state "
            "where group_id=%s",
            (group_id,),
        )
        row = cur.fetchone()

    with db.cursor() as cur:
        if row:
            if row[0] > last_modified:
                return row[1]  # type: ignore

            cur.execute(
                "update source_group_state "
                "set last_modified= %s, etag=%s "
                "where group_id= %s",
                (last_modified, etag, group_id),
            )
        else:
            cur.execute(
                "insert into source_group_state (group_id, last_modified, "
                "etag)"
                "values (%s, %s, %s)",
                (group_id, last_modified, etag),
            )

        return etag


def get_state(db: DB, group_id: int) -> ty.Optional[ty.Tuple[datetime, str]]:
    """Get group entries last modified information.

    Return:
        (last modified date, etag)
    """
    with db.cursor() as cur:
        cur.execute(
            "select last_modified, etag from source_group_state "
            "where group_id= %s",
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
            "select count(1) from source_groups where user_id=%s", (user_id,)
        )
        if not cur.fetchone()[0]:
            raise common.OperationError("can't delete last group")

    with db.cursor() as cur:
        cur.execute(
            "select count(1) from sources where group_id=%s", (group_id,)
        )
        if cur.fetchone()[0]:
            # there are sources in group find destination group
            dst_group_id = _find_dst_group(db, user_id, group_id)
            cur.execute(
                "update sources set group_id= %s where group_id=%s",
                (dst_group_id, group_id),
            )
            _LOG.debug("moved %d sources", cur.rowcount)

    with db.cursor() as cur:
        cur.execute("delete from source_groups where id= %s", (group_id,))


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
            "select id from source_groups where user_id= %s and name='main' "
            "and id != %s order by id limit 1",
            (user_id, group_id),
        )
        row = cur.fetchone()

    if row:
        return row[0]  # type: ignore

    with db.cursor() as cur:
        cur.execute(
            "select id from source_groups where user_id= %s "
            "and id != %s order by id limit 1",
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
                "select min(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id > %s and e.read_mark=%s and s.group_id=%s",
                (entry_id, model.EntryReadMark.UNREAD, group_id),
            )
        else:
            cur.execute(
                "select min(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id > %s and s.group_id=%s",
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
                "select max(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id < %s and e.read_mark=%s and s.group_id=%s",
                (entry_id, model.EntryReadMark.UNREAD, group_id),
            )
        else:
            cur.execute(
                "select max(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id < %s and s.group_id=%s",
                (entry_id, group_id),
            )

        row = cur.fetchone()
        return row[0] if row else None
