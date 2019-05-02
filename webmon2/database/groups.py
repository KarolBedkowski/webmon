#!/usr/bin/python3
"""

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""
import logging
import typing as ty

from webmon2 import model
from . import _dbcommon as dbc

_LOG = logging.getLogger(__file__)


def get_groups(db, user_id: int) -> ty.List[model.SourceGroup]:
    assert user_id
    cur = db.cursor()
    cur.execute(_GET_SOURCE_GROUPS_SQL, (user_id, ))
    groups = [model.SourceGroup(id, name, unread, user_id)
              for id, name, user_id, unread in cur]
    return groups


def get_group(db, id_) -> model.SourceGroup:
    cur = db.cursor()
    cur.execute(
        "select id as source_group_id, name as source_group_name, "
        "user_id as source_group_user_id from source_groups where id=?",
        (id_, ))
    row = cur.fetchone()
    if not row:
        raise dbc.NotFound
    return _source_group_from_row(row)


def save_group(db, group: model.SourceGroup):
    cur = db.cursor()
    if group.id is None:
        cur.execute(
            "insert into source_groups (name, user_id) values (?, ?)",
            (group.name, group.user_id))
        group.id = cur.lastrowid
    else:
        cur.execute("update source_groups set name=? where id=?",
                    (group.name, group.id))
    db.commit()
    return group


def get_next_unread_group(db, user_id: int) -> ty.Optional[int]:
    cur = db.cursor()
    cur.execute(
        "select group_id "
        "from sources s join entries e on e.source_id = s.id "
        "where e.read_mark = 0 and s.user_id=? "
        "order by e.id limit 1", (user_id, ))
    row = cur.fetchone()
    return row[0] if row else None


def mark_read(db, group_id: int, min_id=None, max_id=None, read=True) -> int:
    assert group_id, "no group id"
    read = 1 if read else 0
    _LOG.info("group_mark_read group_id=%r,max_id=%r, read=%r",
              group_id, max_id, read)
    cur = db.cursor()
    if max_id:
        cur.execute(
            "update entries set read_mark=? where source_id in "
            "( select id from sources where group_id=?) and id <= ? "
            " and id >= ?", (read, group_id, max_id, min_id or 0))
    else:
        cur.execute(
            "update entries set read_mark=? where source_id in "
            "( select id from sources where group_id=?)",
            (read, group_id))
    changed = cur.rowcount
    db.commit()
    return changed


_GET_SOURCE_GROUPS_SQL = """
select sg.id, sg.name, sg.user_id,
    (select count(*)
        from entries e
        join sources s on e.source_id = s.id
        where e.read_mark = 0 and s.group_id = sg.id
    ) as unread
from source_groups sg
where sg.user_id=?
"""


def _source_group_from_row(row) -> model.SourceGroup:
    return model.SourceGroup(row["source_group_id"],
                             row["source_group_name"],
                             row["source_group_user_id"])
