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


def get_all(db, user_id: int) -> ty.List[model.SourceGroup]:
    """ Get all groups for user with number of unread entries """
    assert user_id
    cur = db.cursor()
    cur.execute(_GET_SOURCE_GROUPS_SQL, (user_id, ))
    groups = [model.SourceGroup(id, name, unread, user_id)
              for id, name, user_id, unread in cur]
    return groups


_GET_SQL = """
select id as source_group_id, name as source_group_name,
    user_id as source_group_user_id
from source_groups
where id=?
"""


def get(db, group_id) -> model.SourceGroup:
    """ Get one group. """
    cur = db.cursor()
    cur.execute(_GET_SQL, (group_id, ))
    row = cur.fetchone()
    if not row:
        raise dbc.NotFound
    return _source_group_from_row(row)


def save(db, group: model.SourceGroup) -> model.SourceGroup:
    """ Save / update group """
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


_GET_NEXT_UNREAD_GROUP_SQL = """
select group_id
from sources s join entries e on e.source_id = s.id
where e.read_mark = 0 and s.user_id=?
order by e.id limit 1
"""


def get_next_unread_group(db, user_id: int) -> ty.Optional[int]:
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
    db.commit()
    return changed


def _source_group_from_row(row) -> model.SourceGroup:
    return model.SourceGroup(row["source_group_id"],
                             row["source_group_name"],
                             row["source_group_user_id"])
