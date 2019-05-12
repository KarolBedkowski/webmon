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
from datetime import datetime

from webmon2 import model
from . import _dbcommon as dbc
from . import sources

_ = ty
_LOG = logging.getLogger(__file__)


_GET_ENTRIES_SQL_MAIN = '''
select
    e.id as entry_id,
    e.source_id as entry_source_id,
    e.updated as entry_updated,
    e.created as entry_created,
    e.read_mark as entry_read_mark,
    e.star_mark as entry_star_mark,
    e.status as entry_status,
    e.oid as entry_oid,
    e.title as entry_title,
    e.url as entry_url,
    e.opts as entry_opts,
    e.content as entry_content,
    e.user_id as entry_user_id,
    s.id as source_id, s.group_id as source_group_id, s.kind as source_kind,
    s.name as source_name, s.interval as source_interval,
    s.user_id as source_user_id,
    sg.id as source_group_id, sg.name as source_group_name,
    sg.user_id as source_group_user_id,
    sg.feed as source_group_feed
from entries e
join sources s on s.id = e.source_id
left join source_groups sg on sg.id = s.group_id
'''

_GET_ENTRIES_SQL = _GET_ENTRIES_SQL_MAIN + '''
where e.user_id=%(user_id)s
order by e.id
'''

_GET_UNREAD_ENTRIES_SQL = _GET_ENTRIES_SQL_MAIN + '''
where read_mark = 0 and e.user_id=%(user_id)s
order by e.id
'''

_GET_UNREAD_ENTRIES_BY_SOURCE_SQL = _GET_ENTRIES_SQL_MAIN + '''
where read_mark = 0 and e.source_id=%(source_id)s and e.user_id=%(user_id)s
order by e.id
'''

_GET_ENTRIES_BY_SOURCE_SQL = _GET_ENTRIES_SQL_MAIN + '''
where e.source_id=%(source_id)s and e.user_id=%(user_id)s
order by e.id
'''

_GET_UNREAD_ENTRIES_BY_GROUP_SQL = _GET_ENTRIES_SQL_MAIN + '''
where read_mark = 0 and s.group_id=%(group_id)s and e.user_id=%(user_id)s
order by e.id
'''

_GET_ENTRIES_BY_GROUP_SQL = _GET_ENTRIES_SQL_MAIN + '''
where s.group_id=%(group_id)s and e.user_id=%(user_id)s
order by e.id
'''

_GET_STARRED_ENTRIES_SQL = _GET_ENTRIES_SQL_MAIN + '''
where e.star_mark = 1 and e.user_id=%(user_id)s
order by e.id
'''

_GET_ENTRIES_BY_GROUP_FEED_SQL = _GET_ENTRIES_SQL_MAIN + '''
where s.group_id=%(group_id)s
order by e.id desc
limit 100
'''


def _get_find_sql(source_id: ty.Optional[int], group_id: ty.Optional[int],
                  unread: bool) -> str:
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


def get_starred(db, user_id: int) -> model.Entries:
    """Get all starred entries for given user """
    assert user_id, 'no user_id'
    with db.cursor() as cur:
        cur.execute(_GET_STARRED_ENTRIES_SQL, {'user_id': user_id})
        for row in cur:
            entry = dbc.entry_from_row(row)
            entry.source = dbc.source_from_row(row)
            if entry.source.group_id:
                entry.source.group = dbc.source_group_from_row(row)
            yield entry


def get_total_count(db, user_id: int, source_id=None, group_id=None,
                    unread=True) -> int:
    """ Get number of read/all entries for user/source/group """
    args = {
        'group_id': group_id,
        'source_id': source_id,
        "user_id": user_id,
    }
    if source_id:
        sql = "select count(*) from entries where source_id=%(source_id)s "\
            "and user_id=%(user_id)s"
        if unread:
            sql += " and read_mark=0"
    elif group_id:
        sql = ("select count(*) from entries where source_id in "
               "(select id from sources s where s.group_id=%(group_id)s) "
               "and user_id=%(user_id)s")
        if unread:
            sql += "and read_mark=0"
    else:
        sql = "select count(*) from entries where user_id=%(user_id)s"
        if unread:
            sql += " and read_mark=0"
    with db.cursor() as cur:
        cur.execute(sql, args)
        result = cur.fetchone()[0]
        return result


def find(db, user_id: int, source_id=None, group_id=None, unread=True,
         offset=None, limit=None) -> model.Entries:
    """ Find entries for user/source/group unread or all.
        Limit and offset work only for getting all entries.
    """
    args = {
        'limit': limit or 25,
        'offset': offset or 0,
        'group_id': group_id,
        'source_id': source_id,
        "user_id": user_id,
    }
    sql = _get_find_sql(source_id, group_id, unread)
    if not unread and limit:
        # for unread there is no pagination
        sql += " limit %(limit)s offset %(offset)s"
    with db.cursor() as cur:
        cur.execute(sql, args)
        user_groups = {}  # type: ty.Dict[int, model.SourceGroup]
        for row in cur:
            entry = dbc.entry_from_row(row)
            entry.source = dbc.source_from_row(row)
            if entry.source.group_id:
                group = user_groups.get(entry.source.group_id)
                if not group:
                    group = user_groups[entry.source.group_id] = \
                        dbc.source_group_from_row(row)
                entry.source.group = group
            yield entry


def find_for_feed(db, group_id: int) -> model.Entries:
    """ Find all entries by group feed.
    """
    with db.cursor() as cur:
        cur.execute(_GET_ENTRIES_BY_GROUP_FEED_SQL, {'group_id': group_id})
        group = None  # model.SourceGroup
        for row in cur:
            entry = dbc.entry_from_row(row)
            entry.source = dbc.source_from_row(row)
            if not group:
                group = dbc.source_group_from_row(row)
            entry.source.group = group
            yield entry


_GET_ENTRY_SQL = '''
select
    id as entry_id,
    source_id as entry_source_id,
    updated as entry_updated,
    created as entry_created,
    read_mark as entry_read_mark,
    star_mark as entry_star_mark,
    status as entry_status,
    oid as entry_oid,
    title as entry_title,
    url as entry_url,
    opts as entry_opts,
    content as entry_content,
    user_id as entry_user_id
from entries
'''


def get(db, id_=None, oid=None, with_source=False, with_group=False):
    assert id_ is not None or oid is not None
    with db.cursor() as cur:
        if id_ is not None:
            sql = _GET_ENTRY_SQL + "where id=%(id)s"
        else:
            sql = _GET_ENTRY_SQL + "where oid=%(oid)s"
        cur.execute(sql, {"oid": oid, "id": id_})
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()
        entry = dbc.entry_from_row(row)
        if with_source:
            entry.source = sources.get(db, entry.source_id,
                                       with_group=with_group)
        return entry


_INSERT_ENTRY_SQL = """
INSERT INTO entries (source_id, updated, created,
    read_mark, star_mark, status, oid, title, url, opts, content, user_id)
VALUES (%(source_id)s, %(updated)s, %(created)s,
    %(read_mark)s, %(star_mark)s, %(status)s, %(oid)s, %(title)s, %(url)s,
    %(opts)s, %(content)s, %(user_id)s)
ON CONFLICT (oid) DO NOTHING
RETURNING id
"""

_UPDATE_ENTRY_SQL = """
update entries set source_id=%(source_id)s, updated=%(updated)s,
    created=%(created)s, read_mark=%(read_mark)s, star_mark=%(star_mark)s,
    status=%(status)s, oid=%(oid)s, title=%(title)s, url=%(url)s,
    opts=%(opts)s, content=%(content)s
where id=%(id)s
"""


def save(db, entry: model.Entry) -> model.Entry:
    """ Insert or update entry """
    row = dbc.entry_to_row(entry)
    with db.cursor() as cur:
        if entry.id is None:
            cur.execute(_INSERT_ENTRY_SQL, row)
            entry.id = cur.fetchone()[0]
        else:
            cur.execute(_UPDATE_ENTRY_SQL, row)
    return entry


def save_many(db, entries: model.Entries, source_id: int):
    """ Insert entries; where entry with given oid already exists - is deleted
        TODO: save star_mark for updated
    """
    with db.cursor() as cur:
        # filter updated entries; should be deleted & inserted
        oids_to_delete = [(entry.oid, ) for entry in entries
                          if entry.status == 'updated']
        if oids_to_delete:
            cur.executemany("delete from entries where oid=%s",
                            oids_to_delete)
        _LOG.debug("to del %d, deleted: %d", len(oids_to_delete), cur.rowcount)
        rows = map(dbc.entry_to_row, entries)
        cur.executemany(_INSERT_ENTRY_SQL, rows)


def delete_old(db, user_id: int, max_datetime: datetime):
    """ Delete old entries for given user """
    with db.cursor() as cur:
        cur.execute("delete from entries where star_mark=0 and read_mark=0 "
                    "and updated<%s and user_id=%s", (max_datetime, user_id))
        deleted_entries = cur.rowcount
        cur.execute("delete from history_oids where source_id in "
                    "(select id from sources where user_id=%s) "
                    "and created<%s",
                    (user_id, max_datetime))
        deleted_oids = cur.rowcount
        _LOG.info("delete_old: user: %d, entries: %d, oids: %d",
                  user_id, deleted_entries, deleted_oids)


def mark_star(db, user_id: int, entry_id: int, star=True) -> int:
    """ Change star mark for given entry """
    star = 1 if star else 0
    _LOG.info("mark_star entry_id=%r,star=%r", entry_id, star)
    with db.cursor() as cur:
        cur.execute(
            "update entries set star_mark=%s where id=%s and star_mark=%s "
            "and user_id=%s",
            (star, entry_id, 1-star, user_id))
        changed = cur.rowcount
    _LOG.debug("changed: %d", changed)
    return changed


def check_oids(db, oids: ty.List[str], source_id: int) -> ty.Set[str]:
    """ Check is given oids already exists in history table.
        Insert new and its oids;
    """
    assert source_id
    with db.cursor() as cur:
        result = set()  # type: ty.Set[str]
        for idx in range(0, len(oids), 100):
            part_oids = tuple(oids[idx:idx+100])
            cur.execute(
                "select oid from history_oids "
                "where source_id=%s and oid in %s",
                (source_id, part_oids))
            result.update(row[0] for row in cur)
        new_oids = [oid for oid in oids if oid not in result]
        _LOG.debug("check_oids: check=%r, found=%d new=%d",
                   len(oids), len(result), len(new_oids))
        cur.executemany(
            "insert into history_oids(source_id, oid) values (%s, %s)",
            [(source_id, oid) for oid in new_oids])
    return set(new_oids)


def mark_read(db, user_id: int, entry_id=None, min_id=None,
              max_id=None, read=True):
    """ Change read mark for given entry"""
    assert (entry_id or max_id) and user_id
    read = 1 if read else 0
    _LOG.debug("mark_read entry_id=%r, min_id=%r, max_id=%r, read=%r, "
               "user_id=%r", entry_id, min_id, max_id, read, user_id)
    with db.cursor() as cur:
        if entry_id:
            cur.execute(
                "update entries set read_mark=%s where id=%s "
                "and read_mark=%s and user_id=%s",
                (read, entry_id, 1-read, user_id))
        elif max_id:
            cur.execute(
                "update entries set read_mark=%s "
                "where id<=%s and id>=%s and user_id=%s",
                (read, max_id, min_id or 0, user_id))
        changed = cur.rowcount
    return changed
