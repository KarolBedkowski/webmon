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
from . import binaries, sources

_ = ty
_LOG = logging.getLogger(__name__)


_GET_ENTRIES_SQL_MAIN = """
select
    e.id as entry__id,
    e.source_id as entry__source_id,
    e.updated as entry__updated,
    e.created as entry__created,
    e.read_mark as entry__read_mark,
    e.star_mark as entry__star_mark,
    e.status as entry__status,
    e.oid as entry__oid,
    e.title as entry__title,
    e.url as entry__url,
    e.opts as entry__opts,
    e.content as entry__content,
    e.user_id as entry__user_id,
    e.icon as entry__icon,
    e.score as entry__score,
    s.id as source__id,
    s.group_id as source__group_id,
    s.kind as source__kind,
    s.name as source__name,
    s.interval as source__interval,
    s.user_id as source__user_id,
    s.status as source__status,
    s.mail_report as source__mail_report,
    s.default_score as source__default_score,
    sg.id as source_group__id,
    sg.name as source_group__name,
    sg.user_id as source_group__user_id,
    sg.feed as source_group__feed,
    sg.mail_report as source_group__mail_report
from entries e
join sources s on s.id = e.source_id
left join source_groups sg on sg.id = s.group_id
"""

_GET_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where e.user_id=%(user_id)s
order by e.id
"""
)

_GET_UNREAD_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where read_mark = 0 and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_UNREAD_ENTRIES_BY_SOURCE_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where read_mark = 0 and e.source_id=%(source_id)s and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_ENTRIES_BY_SOURCE_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where e.source_id=%(source_id)s and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_UNREAD_ENTRIES_BY_GROUP_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where read_mark = 0 and s.group_id=%(group_id)s and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_ENTRIES_BY_GROUP_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where s.group_id=%(group_id)s and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_STARRED_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where e.star_mark = 1 and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_ENTRIES_BY_GROUP_FEED_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where s.group_id=%(group_id)s
order by e.id desc
limit 100
"""
)

_GET_HISTORY_ENTRIES_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where e.read_mark = 2 and e.user_id=%(user_id)s
order by e.id
"""
)

_GET_ENTRIES_FULLTEXT_TITLE_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where to_tsvector(title) @@ to_tsquery('pg_catalog.simple', %(query)s)
"""
)

_GET_ENTRIES_FULLTEXT_SQL = (
    _GET_ENTRIES_SQL_MAIN
    + """
where to_tsvector(content || ' ' || title)
        @@ to_tsquery('pg_catalog.simple', %(query)s)
    and e.user_id=%(user_id)s
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


def _yield_entries(cur):
    sources = {}
    groups = {}
    for row in cur:
        entry = model.Entry.from_row(row)
        entry.source = sources.get(entry.source_id)
        if not entry.source:
            entry.source = sources[entry.source_id] = model.Source.from_row(
                row
            )
        group_id = entry.source.group_id
        if group_id and not entry.source.group:
            entry.source.group = groups.get(group_id)
            if not entry.source.group:
                entry.source.group = groups[
                    group_id
                ] = model.SourceGroup.from_row(row)
        yield entry


def get_starred(db, user_id: int) -> model.Entries:
    """Get all starred entries for given user"""
    if not user_id:
        raise ValueError("missing user_id")

    with db.cursor() as cur:
        cur.execute(_GET_STARRED_ENTRIES_SQL, {"user_id": user_id})
        yield from _yield_entries(cur)


def get_history(db, user_id: int) -> model.Entries:
    """Get all entries manually read (read_mark=2) for given user"""
    if not user_id:
        raise ValueError("missing user_id")

    with db.cursor() as cur:
        cur.execute(_GET_HISTORY_ENTRIES_SQL, {"user_id": user_id})
        yield from _yield_entries(cur)


def get_total_count(
    db, user_id: int, source_id=None, group_id=None, unread=True
) -> int:
    """Get number of read/all entries for user/source/group"""
    if not user_id and not source_id and not group_id:
        raise ValueError("missing user_id/source_id/group_id")

    args = {
        "group_id": group_id,
        "source_id": source_id,
        "user_id": user_id,
    }
    if source_id:
        sql = "select count(1) from entries where source_id=%(source_id)s "
    elif group_id:
        sql = (
            "select count(1) from entries e "
            "join sources s on e.source_id = s.id "
            "where s.group_id=%(group_id)s "
        )
    else:
        sql = "select count(1) from entries where user_id=%(user_id)s"
    if unread:
        sql += " and read_mark=0"
    with db.cursor() as cur:
        cur.execute(sql, args)
        result = cur.fetchone()[0]
        return result


def find(
    db,
    user_id: int,
    source_id=None,
    group_id=None,
    unread=True,
    offset=None,
    limit=None,
) -> model.Entries:
    """Find entries for user/source/group unread or all.
    Limit and offset work only for getting all entries.
    """
    args = {
        "limit": limit or 25,
        "offset": offset or 0,
        "group_id": group_id,
        "source_id": source_id,
        "user_id": user_id,
    }
    sql = _get_find_sql(source_id, group_id, unread)
    if limit:
        # for unread there is no pagination
        sql += " limit %(limit)s offset %(offset)s"
    with db.cursor() as cur:
        cur.execute(sql, args)
        user_groups = {}  # type: ty.Dict[int, model.SourceGroup]
        user_sources = {}  # type: ty.Dict[int, model.Source]
        for row in cur:
            entry = model.Entry.from_row(row)
            source_id = entry.source_id
            entry.source = user_sources.get(source_id)
            if not entry.source:
                entry.source = user_sources[source_id] = model.Source.from_row(
                    row
                )
                group_id = entry.source.group_id
                entry.source.group = user_groups.get(group_id)
                if not entry.source.group:
                    entry.source.group = user_groups[
                        group_id
                    ] = model.SourceGroup.from_row(row)
            yield entry


def find_fulltext(
    db,
    user_id: int,
    query: str,
    title_only: bool,
    group_id: ty.Optional[int] = None,
    source_id: ty.Optional[int] = None,
) -> model.Entries:
    """Find entries for user by full-text search on title or title and content.
    Search in source (if given source_id) or in group (if given group_id)
    or in all entries given user
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
        sql += " and e.source_id=%(source_id)s "
    elif group_id:
        sql += " and s.group_id=%(group_id)s "
    else:
        sql += " and e.user_id=%(user_id)s "
    sql += " order by e.id"

    with db.cursor() as cur:
        cur.execute(sql, args)
        user_groups = {}  # type: ty.Dict[int, model.SourceGroup]
        user_sources = {}  # type: ty.Dict[int, model.Source]
        for row in cur:
            entry = model.Entry.from_row(row)
            e_source_id = entry.source_id  # type: int
            entry.source = user_sources.get(e_source_id)
            if not entry.source:
                entry.source = user_sources[
                    e_source_id
                ] = model.Source.from_row(row)
                e_group_id = entry.source.group_id
                entry.source.group = user_groups.get(e_group_id)
                if not entry.source.group:
                    entry.source.group = user_groups[
                        e_group_id
                    ] = model.SourceGroup.from_row(row)
            yield entry


def find_for_feed(db, group_id: int) -> model.Entries:
    """Find all entries by group feed."""
    with db.cursor() as cur:
        cur.execute(_GET_ENTRIES_BY_GROUP_FEED_SQL, {"group_id": group_id})
        group = None  # model.SourceGroup
        for row in cur:
            entry = model.Entry.from_row(row)
            entry.source = model.Source.from_row(row)
            if not group:
                group = model.SourceGroup.from_row(row)
            entry.source.group = group
            yield entry


_GET_ENTRY_SQL = """
select
    id as entry__id,
    source_id as entry__source_id,
    updated as entry__updated,
    created as entry__created,
    read_mark as entry__read_mark,
    star_mark as entry__star_mark,
    status as entry__status,
    oid as entry__oid,
    title as entry__title,
    url as entry__url,
    opts as entry__opts,
    content as entry__content,
    user_id as entry__user_id,
    icon as entry__icon,
    score as entry__score
from entries
"""


def get(db, id_=None, oid=None, with_source=False, with_group=False):
    if not id_ and oid is None:
        raise ValueError("missing id/oid")

    with db.cursor() as cur:
        if id_ is not None:
            sql = _GET_ENTRY_SQL + "where id=%(id)s"
        else:
            sql = _GET_ENTRY_SQL + "where oid=%(oid)s"
        cur.execute(sql, {"oid": oid, "id": id_})
        row = cur.fetchone()
        if not row:
            raise dbc.NotFound()
        entry = model.Entry.from_row(row)
        if with_source:
            entry.source = sources.get(
                db, entry.source_id, with_group=with_group
            )
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
update entries
set source_id=%(entry__source_id)s,
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
where id=%(entry__id)s
"""


def save(db, entry: model.Entry) -> model.Entry:
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


def save_many(db, entries: model.Entries):
    """Insert entries; where entry with given oid already exists - is deleted
    and inserted again; star mark is preserved.
    """
    with db.cursor() as cur:
        # filter updated entries; should be deleted & inserted
        oids_to_delete = [
            (entry.oid,) for entry in entries if entry.status == "updated"
        ]
        if oids_to_delete:
            # find stared entries
            cur.execute(
                "select oid from entries where oid=%s and star_mark=1",
                oids_to_delete,
            )
            marked_oids = {row[0] for row in cur}
            cur.executemany("delete from entries where oid=%s", oids_to_delete)
            _LOG.debug(
                "to del %d, deleted: %d", len(oids_to_delete), cur.rowcount
            )
            # set star mark for updated entries
            if marked_oids:
                for entry in entries:
                    if entry.oid in marked_oids:
                        entry.star_mark = True
        rows = map(model.Entry.to_row, entries)
        cur.executemany(_INSERT_ENTRY_SQL, rows)
    _save_entry_icon(db, entries)


def _save_entry_icon(db, entries):
    saved = set()
    for entry in entries:
        if not entry.icon or entry.icon in saved or not entry.icon_data:
            continue
        content_type, data = entry.icon_data
        binaries.save(db, entry.user_id, content_type, entry.icon, data)
        saved.add(entry.icon)


def delete_old(db, user_id: int, max_datetime: datetime) -> ty.Tuple[int, int]:
    """Delete old entries for given user"""
    with db.cursor() as cur:
        cur.execute(
            "delete from entries where star_mark=0 and read_mark=0 "
            "and updated<%s and user_id=%s",
            (max_datetime, user_id),
        )
        deleted_entries = cur.rowcount
        cur.execute(
            "delete from history_oids where source_id in "
            "(select id from sources where user_id=%s) "
            "and created<%s",
            (user_id, max_datetime),
        )
        deleted_oids = cur.rowcount
        return (deleted_entries, deleted_oids)


def mark_star(db, user_id: int, entry_id: int, star=True) -> int:
    """Change star mark for given entry"""
    star = 1 if star else 0
    _LOG.info("mark_star entry_id=%r,star=%r", entry_id, star)
    with db.cursor() as cur:
        cur.execute(
            "update entries set star_mark=%s where id=%s and star_mark=%s",
            (star, entry_id, 1 - star),
        )
        changed = cur.rowcount
    _LOG.debug("changed: %d", changed)
    return changed


def check_oids(db, oids: ty.List[str], source_id: int) -> ty.Set[str]:
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
                "select oid from history_oids "
                "where source_id=%s and oid in %s",
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
        cur.executemany(
            "insert into history_oids(source_id, oid) values (%s, %s)",
            [(source_id, oid) for oid in new_oids],
        )
    return set(new_oids)


def mark_read(
    db, user_id: int, entry_id=None, min_id=None, max_id=None, read=1, ids=None
):
    """Change read mark for given entry"""
    if not (entry_id or (user_id and (max_id or ids))):
        raise ValueError("missing entry_id/max_id/ids/user")

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
                "update entries set read_mark=%s where id=%s", (read, entry_id)
            )
        elif ids:
            cur.execute(
                "UPDATE Entries SET read_mark=%s "
                "WHERE id=ANY(%s) AND user_id=%s",
                (read, ids, user_id),
            )
        elif max_id:
            cur.execute(
                "update entries set read_mark=%s "
                "where id<=%s and id>=%s and user_id=%s",
                (read, max_id, min_id or 0, user_id),
            )
        changed = cur.rowcount
    return changed


def mark_all_read(db, user_id: int, max_date=None):
    with db.cursor() as cur:
        if max_date:
            cur.execute(
                "update entries set read_mark=1 where user_id=%s "
                "and read_mark=0 and updated<%s",
                (user_id, max_date),
            )
        else:
            cur.execute(
                "update entries set read_mark=1 where user_id=%s "
                "and read_mark=0",
                (user_id,),
            )
        return cur.rowcount


def find_next_entry_id(
    db, user_id: int, entry_id: int, unread=True
) -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "select min(e.id) "
                "from entries e "
                "where e.id > %s and e.read_mark=0 and e.user_id=%s",
                (entry_id, user_id),
            )
        else:
            cur.execute(
                "select min(e.id) "
                "from entries e  "
                "where e.id > %s and e.user_id=%s",
                (entry_id, user_id),
            )
        row = cur.fetchone()
        return row[0] if row else None


def find_prev_entry_id(
    db, user_id: int, entry_id: int, unread=True
) -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "select max(e.id) "
                "from entries e "
                "where e.id < %s and e.read_mark=0 and e.user_id=%s",
                (entry_id, user_id),
            )
        else:
            cur.execute(
                "select max(e.id) "
                "from entries e "
                "where e.id < %s and e.user_id=%s",
                (entry_id, user_id),
            )
        row = cur.fetchone()
        return row[0] if row else None
