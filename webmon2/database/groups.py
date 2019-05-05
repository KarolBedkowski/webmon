#!/usr/bin/python3
"""

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""
import logging
import typing as ty
import random
import hashlib
from datetime import datetime

from webmon2 import model
from . import _dbcommon as dbc

_LOG = logging.getLogger(__file__)

_GET_SOURCE_GROUPS_SQL = """
select sg.id, sg.name, sg.user_id, sg.feed,
    (select count(*)
        from entries e
        join sources s on e.source_id = s.id
        where e.read_mark = 0 and s.group_id = sg.id
    ) as unread
from source_groups sg
where sg.user_id=?
"""


def get_all(db, user_id: int) -> ty.List[model.SourceGroup]:
    """ Get all groups for user with number of unread entries """
    assert user_id
    cur = db.cursor()
    cur.execute(_GET_SOURCE_GROUPS_SQL, (user_id, ))
    groups = [model.SourceGroup(id, name, user_id, feed, unread)
              for id, name, user_id, feed, unread in cur]
    return groups


_GET_SQL = """
select id as source_group_id, name as source_group_name,
    user_id as source_group_user_id, feed as source_group_feed
from source_groups
where id=?
"""


def get(db, group_id) -> model.SourceGroup:
    """ Get one group. """
    cur = db.cursor()
    cur.execute(_GET_SQL, (group_id, ))
    row = cur.fetchone()
    if not row:
        raise dbc.NotFound()
    return dbc.source_group_from_row(row)


_GET_BY_FEED_SQL = """
select id as source_group_id, name as source_group_name,
    user_id as source_group_user_id, feed as source_group_feed
from source_groups
where feed=?
"""


def get_by_feed(db, feed: str) -> model.SourceGroup:
    """ Get group by feed """
    if feed == 'off':
        raise dbc.NotFound()
    cur = db.cursor()
    cur.execute(_GET_BY_FEED_SQL, (feed, ))
    row = cur.fetchone()
    if not row:
        raise dbc.NotFound()
    return dbc.source_group_from_row(row)


def get_last_update(db, group_id: int) -> ty.Optional[datetime]:
    """ Find last update time for entries in group """
    cur = db.cursor()
    cur.execute(
        "select max(datetime(coalesce(updated, created))) from entries "
        "where source_id in (select id from sources where group_id=?)",
        (group_id, ))
    row = cur.fetchone()
    _LOG.debug("row: %s", row[0])
    return datetime.fromisoformat(row[0]) if row and row[0] else None


def save(db, group: model.SourceGroup) -> model.SourceGroup:
    """ Save / update group """
    cur = db.cursor()
    if not group.feed:
        group.feed = _generate_group_feed(cur)

    if group.id is None:
        cur.execute(
            "insert into source_groups (name, user_id, feed) values (?, ?, ?)",
            (group.name, group.user_id, group.feed))
        group.id = cur.lastrowid
    else:
        cur.execute("update source_groups set name=?, feed=? where id=?",
                    (group.name, group.feed, group.id))
    return group


def _generate_group_feed(cur):
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    while True:
        feed = ''.join(random.SystemRandom().choice(chars) for _ in range(32))

        cur.execute('select 1 from source_groups where feed=?', (feed, ))
        if not cur.fetchone():
            return feed


_GET_NEXT_UNREAD_GROUP_SQL = """
select group_id
from sources s join entries e on e.source_id = s.id
where e.read_mark = 0 and s.user_id=?
order by e.id limit 1
"""


def get_next_unread_group(db, user_id: int) -> ty.Optional[int]:
    """ Find group id with unread entries """
    cur = db.cursor()
    cur.execute(_GET_NEXT_UNREAD_GROUP_SQL, (user_id, ))
    row = cur.fetchone()
    return row[0] if row else None


_MARK_READ_SQL = """
update entries
set read_mark=1
where source_id in (select id from sources where group_id=:group_id)
    and id <= :max_id and id >= :min_id and read_mark=0"
"""


def mark_read(db, group_id: int, max_id, min_id=0) -> int:
    """ Mark entries in given group read. """
    assert group_id, "no group id"
    assert max_id
    cur = db.cursor()
    cur.execute(_MARK_READ_SQL, {"group_id": group_id, "min_id": min_id,
                                 "max_id": max_id})
    changed = cur.rowcount
    return changed


def update_state(db, group_id: int, last_modified: datetime) -> str:
    """ Save (update or insert) group last modified information  """
    etag_h = hashlib.md5(str(group_id).encode('ascii'))
    etag_h.update(str(last_modified).encode('ascii'))
    etag = etag_h.hexdigest()

    cur = db.cursor()
    cur.execute("select last_modified, etag from source_group_state "
                "where group_id=?", (group_id, ))
    row = cur.fetchone()
    if row:
        if row[0] > last_modified:
            return row[1]
        cur.execute(
            "update source_group_state "
            "set last_modified=?, etag=? "
            "where group_id=?", (last_modified, etag, group_id))
    else:
        cur.execute(
            "insert into source_group_state (group_id, last_modified, etag)"
            "values (?, ?, ?)", (group_id, last_modified, etag))
    return etag


def get_state(db, group_id: int) -> ty.Optional[ty.Tuple[datetime, str]]:
    """ Get group entries last modified information
        Returns: last modified date and etag
    """
    cur = db.cursor()
    cur.execute(
        "select last_modified, etag from source_group_state where group_id=?",
        (group_id, ))
    row = cur.fetchone()
    if not row:
        last_updated = get_last_update(db, group_id)
        if not last_updated:
            return None
        etag = update_state(db, group_id, last_updated)
        return (last_updated, etag)
    return row[0], row[1]
