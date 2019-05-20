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

from webmon2 import model, common
from . import _dbcommon as dbc

_LOG = logging.getLogger(__name__)

_GET_SOURCE_GROUPS_SQL = """
select sg.id, sg.name, sg.user_id, sg.feed,
    (select count(*)
        from entries e
        join sources s on e.source_id = s.id
        where e.read_mark = 0 and s.group_id = sg.id
    ) as unread,
    (select count(*) from sources s where s.group_id = sg.id)
        as sources_count
from source_groups sg
where sg.user_id= %s
order by sg.name
"""


def get_all(db, user_id: int) -> ty.List[model.SourceGroup]:
    """ Get all groups for user with number of unread entries """
    assert user_id
    with db.cursor() as cur:
        cur.execute(_GET_SOURCE_GROUPS_SQL, (user_id, ))
        groups = [
            model.SourceGroup(
                id=id, name=name, user_id=user_id, feed=feed,
                unread=unread, sources_count=sources_count)
            for id, name, user_id, feed, unread, sources_count in cur]
        return groups


_GET_SQL = """
select id as source_group_id, name as source_group_name,
    user_id as source_group_user_id, feed as source_group_feed
from source_groups
where id= %s
"""


def get(db, group_id) -> model.SourceGroup:
    """ Get one group. """
    with db.cursor() as cur:
        cur.execute(_GET_SQL, (group_id, ))
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()
        return dbc.source_group_from_row(row)


_FIND_SQL = """
select id as source_group_id, name as source_group_name,
    user_id as source_group_user_id, feed as source_group_feed
from source_groups
where name=%s and user_id=%s
"""


def find(db, user_id: int, name: str) -> ty.Optional[model.SourceGroup]:
    """ Get one group. """
    with db.cursor() as cur:
        cur.execute(_FIND_SQL, (name, user_id))
        row = cur.fetchone()
        return dbc.source_group_from_row(row) if row else None


_GET_BY_FEED_SQL = """
select id as source_group_id, name as source_group_name,
    user_id as source_group_user_id, feed as source_group_feed
from source_groups
where feed= %s
"""


def get_by_feed(db, feed: str) -> model.SourceGroup:
    """ Get group by feed """
    if feed == 'off':
        raise dbc.NotFound()
    with db.cursor() as cur:
        cur.execute(_GET_BY_FEED_SQL, (feed, ))
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()
        return dbc.source_group_from_row(row)


def get_last_update(db, group_id: int) -> ty.Optional[datetime]:
    """ Find last update time for entries in group """
    with db.cursor() as cur:
        cur.execute(
            "select max(datetime(coalesce(updated, created))) from entries "
            "where source_id in (select id from sources where group_id= %s)",
            (group_id, ))
        row = cur.fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None


def save(db, group: model.SourceGroup) -> model.SourceGroup:
    """ Save / update group """
    with db.cursor() as cur:
        if not group.feed:
            group.feed = _generate_group_feed(cur)

        if group.id is None:
            cur.execute(
                "insert into source_groups (name, user_id, feed) "
                "values (%s, %s, %s) returning id",
                (group.name, group.user_id, group.feed))
            group.id = cur.fetchone()[0]
        else:
            cur.execute(
                "update source_groups set name= %s, feed=%s where id=%s",
                (group.name, group.feed, group.id))
        return group


def _generate_group_feed(cur):
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    while True:
        feed = ''.join(random.SystemRandom().choice(chars) for _ in range(32))

        cur.execute('select 1 from source_groups where feed= %s', (feed, ))
        if not cur.fetchone():
            return feed


_GET_NEXT_UNREAD_GROUP_SQL = """
select group_id
from sources s join entries e on e.source_id = s.id
where e.read_mark = 0 and s.user_id= %s
order by e.id limit 1
"""


def get_next_unread_group(db, user_id: int) -> ty.Optional[int]:
    """ Find group id with unread entries """
    with db.cursor() as cur:
        cur.execute(_GET_NEXT_UNREAD_GROUP_SQL, (user_id, ))
        row = cur.fetchone()
        return row[0] if row else None


_MARK_READ_SQL = """
update entries
set read_mark=1
where source_id in (select id from sources where group_id=%(group_id)s)
    and id<=%(max_id)s and id>=%(min_id)s and read_mark=0
    and user_id=%(user_id)s
"""


def mark_read(db, user_id: int, group_id: int, max_id, min_id=0) -> int:
    """ Mark entries in given group read. """
    assert group_id, "no group id"
    assert max_id
    with db.cursor() as cur:
        cur.execute(_MARK_READ_SQL, {"group_id": group_id, "min_id": min_id,
                                     "max_id": max_id, "user_id": user_id})
        changed = cur.rowcount
        return changed


def update_state(db, group_id: int, last_modified: datetime) -> str:
    """ Save (update or insert) group last modified information  """
    etag_h = hashlib.md5(str(group_id).encode('ascii'))
    etag_h.update(str(last_modified).encode('ascii'))
    etag = etag_h.hexdigest()

    with db.cursor() as cur:
        cur.execute("select last_modified, etag from source_group_state "
                    "where group_id=%s", (group_id, ))
        row = cur.fetchone()
        if row:
            if row[0] > last_modified:
                return row[1]
            cur.execute(
                "update source_group_state "
                "set last_modified= %s, etag=%s "
                "where group_id= %s", (last_modified, etag, group_id))
        else:
            cur.execute(
                "insert into source_group_state (group_id, last_modified, "
                "etag)"
                "values (%s, %s, %s)", (group_id, last_modified, etag))
        return etag


def get_state(db, group_id: int) -> ty.Optional[ty.Tuple[datetime, str]]:
    """ Get group entries last modified information
        Returns: last modified date and etag
    """
    with db.cursor() as cur:
        cur.execute(
            "select last_modified, etag from source_group_state "
            "where group_id= %s",
            (group_id, ))
        row = cur.fetchone()
        if not row:
            last_updated = get_last_update(db, group_id)
            if not last_updated:
                return None
            etag = update_state(db, group_id, last_updated)
            return (last_updated, etag)
        return row[0], row[1]


def delete(db, user_id: int, group_id: int):
    """ Delete group; move existing sources to main (or first) group

    TODO: recalculate state
    """
    with db.cursor() as cur:
        cur.execute('select count(1) from source_groups where user_id=%s',
                    (user_id, ))
        if not cur.fetchone()[0]:
            raise common.OperationError("can't delete last group")

        cur.execute("select count(1) from sources where group_id=%s",
                    (group_id, ))
        if cur.fetchone()[0]:
            # there are sources in group
            # find main
            dst_group_id = _find_dst_group(db, user_id, group_id)
            cur.execute('update sources set group_id= %s where group_id=%s',
                        (dst_group_id, group_id))
            _LOG.debug("moved %d sources", cur.rowcount)

        cur.execute("delete from source_groups where id= %s", (group_id, ))
        cur.close()


def _find_dst_group(db, user_id: int, group_id: int):
    with db.cursor() as cur:
        cur.execute(
            "select id from source_groups where user_id= %s and name='main' "
            "and id != %s order by id limit 1", (user_id, group_id))
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            "select id from source_groups where user_id= %s "
            "and id != %s order by id limit 1", (user_id, group_id))
        row = cur.fetchone()
        if row:
            return row[0]
        raise common.OperationError("can't find destination group for sources")


def find_next_entry_id(db, group_id: int, entry_id: int, unread=True) \
        -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "select min(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id > %s and e.read_mark=0 and s.group_id=%s",
                (entry_id, group_id))
        else:
            cur.execute(
                "select min(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id > %s and s.group_id=%s",
                (entry_id, group_id))
        row = cur.fetchone()
        return row[0] if row else None


def find_prev_entry_id(db, group_id: int, entry_id: int, unread=True) \
        -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "select max(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id < %s and e.read_mark=0 and s.group_id=%s",
                (entry_id, group_id))
        else:
            cur.execute(
                "select max(e.id) "
                "from entries e join sources s on s.id = e.source_id "
                "where e.id < %s and s.group_id=%s",
                (entry_id, group_id))
        row = cur.fetchone()
        return row[0] if row else None
