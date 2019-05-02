#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""

"""

import logging
import typing as ty

import json

from webmon2 import model
from . import _dbcommon as dbc
from . import groups

_ = ty
_LOG = logging.getLogger(__file__)


def find(db, user_id, group_id=None) -> ty.Iterable[model.Source]:
    cur = db.cursor()
    user_groups = {g.id: g for g in groups.get_groups(db, user_id)}
    if group_id is None:
        cur.execute(_GET_SOURCES_SQL, (user_id, ))
    else:
        cur.execute(_GET_SOURCES_BY_GROUP_SQL, (group_id, user_id))
    for row in cur:
        source = dbc.source_from_row(row)
        source.state = dbc.state_from_row(row)
        source.unread = row['unread']
        source.group = user_groups.get(source.group_id) \
            if source.group_id else None
        yield source


def get(db, id_, with_state=False, with_group=True):
    cur = db.cursor()
    cur.execute(_GET_SOURCE_SQL, (id_, ))
    row = cur.fetchone()
    if row is None:
        raise dbc.NotFound()

    source = dbc.source_from_row(row)
    if with_state:
        source.state = get_state(db, source.id)
    if with_group and source.group_id:
        source.group = groups.get_group(db, source.group_id)

    return source


def save(db, source: model.Source):
    cur = db.cursor()
    row = dbc.source_to_row(source)
    if source.id is None:
        cur.execute(_INSERT_SOURCE_SQL, row)
        source.id = cur.lastrowid
        state = model.SourceState.new(source.id)
        db.save_state(state)
    else:
        cur.execute(_UPDATE_SOURCE_SQL, row)
    db.commit()
    return source


def delete(db, source_id: int) -> int:
    cur = db.cursor()
    cur.execute("delete from sources where id=?", (source_id, ))
    updated = cur.rowcount
    db.commit()
    return updated


def update_filter(db, source_id: int, filter_idx: int,
                  filter_: ty.Dict[str, ty.Any]):
    source = get(db, source_id, False, False)
    if not source.filters:
        source.filters = [filter_]
    elif 0 <= filter_idx < len(source.filters):
        source.filters[filter_idx] = filter_
    else:
        source.filters.append(filter_)
    save(db, source)


def delete_filter(db, source_id: int, filter_idx: int):
    source = get(db, source_id, False, False)
    if source.filters and filter_idx < len(source.filters):
        del source.filters[filter_idx]
        save(db, source)


def move_filter(db, source_id: int, filter_idx: int, direction: str):
    source = get(db, source_id, False, False)
    if not source.filters or filter_idx >= len(source.filters) \
            or len(source.filters) == 1:
        return
    if direction == 'up' and filter_idx > 0:
        source.filters[filter_idx - 1], source.filters[filter_idx] = \
            source.filters[filter_idx], source.filters[filter_idx - 1]
        save(db, source)
    elif direction == 'down' and filter_idx < len(source.filters) - 2:
        source.filters[filter_idx + 1], source.filters[filter_idx] = \
            source.filters[filter_idx], source.filters[filter_idx + 1]
        save(db, source)


def get_state(db, source_id):
    cur = db.cursor()
    cur.execute(_GET_STATE_SQL, (source_id, ))
    row = cur.fetchone()
    return dbc.state_from_row(row) if row else None


def save_state(db, state):
    cur = db.cursor()
    row = dbc.state_to_row(state)
    cur.execute("delete from source_state where source_id=?",
                (state.source_id,))
    cur.execute(_INSERT_STATE_SQL, row)
    db.commit()
    return state


def get_sources_to_fetch(db):
    cur = db.cursor()
    ids = [row[0] for row in
           cur.execute(
               "select source_id from source_state "
               "where next_update <= datetime('now', 'localtime')")
           ]
    return ids


def refresh(db, source_id=None, group_id=None):
    cur = db.cursor()
    args = {"group_id": group_id, "source_id": source_id}
    sql = ["update source_state "
           "set next_update=datetime('now', 'localtime') "
           "where (last_update is null or "
           "last_update < datetime('now', 'localtime', '-1 minutes'))"]
    if group_id:
        sql.append(
            "and source_id in "
            "(select id from sources where group_id=:group_id)")
    elif source_id:
        sql.append("and source_id=:source_id")
    cur.execute(" ".join(sql), args)
    updated = cur.rowcount
    db.commit()
    return updated


def refresh_errors(db):
    cur = db.cursor()
    cur.execute("update source_state set next_update=datetime('now') "
                "where status='error'")
    updated = cur.rowcount
    db.commit()
    return updated


def mark_read(db, source_id: int, min_id=None, max_id=None, read=True):
    read = 1 if read else 0
    _LOG.info("source_mark_read source_id=%r, max_id=%r, read=%r",
              source_id, max_id, read)
    cur = db.cursor()
    if max_id:
        cur.execute(
            "update entries set read_mark=? where source_id = ? "
            "and id <= ? and read_mark=? and id >= ?",
            (read, source_id, max_id, 1-read, min_id or 0))
    else:
        cur.execute(
            "update entries set read_mark=? where source_id = ?",
            (read, source_id))
    changed = cur.rowcount
    _LOG.debug("total changes: %d, changed: %d", db.total_changes,
               changed)
    db.commit()
    return changed


def get_filter_state(db, source_id: int, filter_name: str) \
        -> ty.Optional[ty.Dict[str, ty.Any]]:
    cur = db.cursor()
    cur.execute('select state from filters_state '
                'where source_id=? and filter_name=?',
                (source_id, filter_name))
    row = cur.fetchone()
    if not row:
        return None
    return json.loads(row[0]) if isinstance(row[0], str) and row[0] \
        else row[0]


def put_filter_state(db, source_id: int, filter_name: str, state):
    cur = db.cursor()
    cur.execute('delete from filters_state '
                'where source_id=? and filter_name=?',
                (source_id, filter_name))
    if state is not None:
        state = json.dumps(state)
        cur.execute(
            'insert into filter_name (source_id, filter_name, state) '
            'values(?, ?, ?)', (source_id, filter_name, state))
    db.commit()


_GET_SOURCE_SQL = """
select id as source_id, group_id as source_group_id,
    kind as source_kind, name as source_name, interval as source_interval,
    settings as source_settings, filters as source_filters,
    user_id as source_user_id
from sources where id=?
"""

_GET_SOURCES_SQL_BASE = """
select s.id as source_id, s.group_id as source_group_id,
    s.kind as source_kind, s.name as source_name,
    s.interval as source_interval, s.settings as source_settings,
    s.filters as source_filters,
    s.user_id as source_user_id,
    ss.source_id as source_state_source_id,
    ss.next_update as source_state_next_update,
    ss.last_update as source_state_last_update,
    ss.last_error as source_state_last_error,
    ss.error_counter as source_state_error_counter,
    ss.success_counter as source_state_success_counter,
    ss.status as source_state_status,
    ss.error as source_state_error,
    ss.state as source_state_state,
    (select count(*)
        from entries where source_id=s.id and read_mark=0) as unread
from sources s
left join source_state ss on ss.source_id = s.id
"""

_GET_SOURCES_SQL = _GET_SOURCES_SQL_BASE + """
where s.user_id=?
order by s.name """

_GET_SOURCES_BY_GROUP_SQL = _GET_SOURCES_SQL_BASE + """
where group_id = ? and s.user_id = ?
order by s.name """

_INSERT_SOURCE_SQL = """
insert into sources (group_id, kind, interval, settings, filters,
    user_id, name)
    values (:group_id, :kind, :interval, :settings, :filters, :user_id, :name)
"""

_UPDATE_SOURCE_SQL = """
update sources
set group_id=:group_id, kind=:kind, name=:name, interval=:interval,
    settings=:settings, filters=:filters
where id=:id
"""

_GET_STATE_SQL = """
select source_id as source_state_source_id,
    next_update as source_state_next_update,
    last_update as source_state_last_update,
    last_error as source_state_last_error,
    error_counter as source_state_error_counter,
    success_counter as source_state_success_counter,
    status as source_state_status,
    error as source_state_error,
    state as source_state_state
from source_state where source_id=?
"""

_INSERT_STATE_SQL = """
insert into source_state(source_id, next_update, last_update, last_error,
    error_counter, success_counter, status, error, state)
values (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
