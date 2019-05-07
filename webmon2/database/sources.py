#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Access & manage sources
"""
import json
import sqlite3
import time
import logging
import typing as ty
import datetime

from webmon2 import model
from . import _dbcommon as dbc
from . import groups

_ = ty
_LOG = logging.getLogger(__file__)

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
where s.user_id=%(user_id)s
order by s.name """

_GET_SOURCES_BY_GROUP_SQL = _GET_SOURCES_SQL_BASE + """
where group_id = %(group_id)s and s.user_id = %(user_id)s
order by s.name """


def get_all(db, user_id: int, group_id=None) -> ty.Iterable[model.Source]:
    """ Get all sources for given user and (optional) in group.
        Include state and number of unread entries
    """
    cur = db.cursor()
    user_groups = {g.id: g for g in groups.get_all(db, user_id)}
    args = {"user_id": user_id, "group_id": group_id}
    sql = _GET_SOURCES_SQL if group_id is None else _GET_SOURCES_BY_GROUP_SQL
    cur.execute(sql, args)
    for row in cur:
        source = dbc.source_from_row(row)
        source.state = _state_from_row(row)
        source.unread = row['unread']
        source.group = user_groups.get(source.group_id) \
            if source.group_id else None
        yield source
    cur.close()


_GET_SOURCE_SQL = """
select id as source_id, group_id as source_group_id,
    kind as source_kind, name as source_name, interval as source_interval,
    settings as source_settings, filters as source_filters,
    user_id as source_user_id
from sources where id=%s
"""


def get(db, id_: int, with_state=False, with_group=True) -> model.Source:
    """ Get one source with optionally with state and group info """
    cur = db.cursor()
    cur.execute(_GET_SOURCE_SQL, (id_, ))
    row = cur.fetchone()
    cur.close()
    if row is None:
        raise dbc.NotFound()

    source = dbc.source_from_row(row)
    if with_state:
        source.state = get_state(db, source.id)
    if with_group and source.group_id:
        source.group = groups.get(db, source.group_id)

    return source


_INSERT_SOURCE_SQL = """
insert into sources (group_id, kind, interval, settings, filters,
    user_id, name)
    values (%(group_id)s, %(kind)s, %(interval)s, %(settings)s, %(filters)s, %(user_id)s, %(name)s)
returning id
"""

_UPDATE_SOURCE_SQL = """
update sources
set group_id=%(group_id)s, kind=%(kind)s, name=%(name)s, interval=%(interval)s,
    settings=%(settings)s, filters=%(filters)s
where id=%(id)s
"""


def save(db, source: model.Source) -> model.Source:
    """ Insert or update source """
    cur = db.cursor()
    row = dbc.source_to_row(source)
    if source.id is None:
        cur.execute(_INSERT_SOURCE_SQL, row)
        source.id = cur.fetchone()[0]
        # create state for new source
        state = model.SourceState.new(source.id)
        save_state(db, state)
    else:
        cur.execute(_UPDATE_SOURCE_SQL, row)
    cur.close()
    return source


def delete(db, source_id: int) -> int:
    """ Delete source """
    cur = db.cursor()
    cur.execute("delete from sources where id=%s", (source_id, ))
    updated = cur.rowcount
    cur.close()
    return updated


def update_filter(db, source_id: int, filter_idx: int,
                  filter_: ty.Dict[str, ty.Any]):
    """ Append or update filter in given source """
    source = get(db, source_id, False, False)
    if not source.filters:
        source.filters = [filter_]
    elif 0 <= filter_idx < len(source.filters):
        source.filters[filter_idx] = filter_
    else:
        source.filters.append(filter_)
    save(db, source)


def delete_filter(db, source_id: int, filter_idx: int):
    """ Delete filter in source """
    source = get(db, source_id, False, False)
    if source.filters and filter_idx < len(source.filters):
        del source.filters[filter_idx]
        save(db, source)


def move_filter(db, source_id: int, filter_idx: int, direction: str):
    """ Change position of given filter in source """
    assert direction in ('up', 'down')
    source = get(db, source_id, False, False)
    if not source.filters or filter_idx >= len(source.filters) \
            or len(source.filters) == 1:
        return
    if direction == 'up':
        if filter_idx <= 0:
            return
        source.filters[filter_idx - 1], source.filters[filter_idx] = \
            source.filters[filter_idx], source.filters[filter_idx - 1]
        save(db, source)
    elif direction == 'down':
        if filter_idx >= len(source.filters) - 2:
            return
        source.filters[filter_idx + 1], source.filters[filter_idx] = \
            source.filters[filter_idx], source.filters[filter_idx + 1]
        save(db, source)


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
from source_state where source_id=%s
"""


def get_state(db, source_id: int) -> ty.Optional[model.SourceState]:
    """ Get state for given source """
    cur = db.cursor()
    cur.execute(_GET_STATE_SQL, (source_id, ))
    row = cur.fetchone()
    state = _state_from_row(row) if row else None
    cur.close()
    return state


_INSERT_STATE_SQL = """
insert into source_state(source_id, next_update, last_update, last_error,
    error_counter, success_counter, status, error, state)
values (%(source_id)s, %(next_update)s, %(last_update)s, %(last_error)s,
    %(error_counter)s, %(success_counter)s, %(status)s, %(error)s, %(state)s)
"""

_UPDATE_STATE_SQL = """
update source_state
set  next_update=%(next_update)s,
     last_update=%(last_update)s,
     last_error=%(last_error)s,
     error_counter=%(error_counter)s,
     success_counter=%(success_counter)s,
     status=%(status)s,
     error=%(error)s,
     state=%(state)s
where source_id=%(source_id)s
"""


def save_state(db, state: model.SourceState) -> model.SourceState:
    """ Save (replace) source state """
    row = _state_to_row(state)
    while True:
        cur = None
        try:
            cur = db.cursor()
            cur.execute("delete from source_state where source_id=%s",
                        (state.source_id,))
            cur.close()
            cur = db.cursor()
            cur.execute(_INSERT_STATE_SQL, row)
            _LOG.debug("OK")
        except sqlite3.OperationalError as err:
            _LOG.warning(
                "delete source_state OperationalError, sleeping, %s: %s",
                state, str(err))
        else:
            break
        finally:
            if cur:
                cur.close()
        time.sleep(1)
    return state


def get_sources_to_fetch(db) -> ty.List[int]:
    """ Find sources with next update state in past """
    cur = db.cursor()
    cur.execute(
        "select source_id from source_state "
        "where next_update <= %s",
        (datetime.datetime.now(), ))

    ids = [row[0] for row in cur]
    cur.close()
    return ids


_REFRESH_SQL = """
update source_state
set next_update=now()
where (last_update is null
    or last_update < now() - '-1 minutes'::interval)
"""


def refresh(db, user_id=None, source_id=None, group_id=None) -> int:
    """ Mark source to refresh; return founded sources """
    assert user_id or source_id or group_id
    sql = _REFRESH_SQL
    if group_id:
        sql += ("and source_id in "
                "(select id from sources where group_id=%(group_id)s)")
    elif source_id:
        sql += "and source_id=%(source_id)s"
    else:
        sql += ("and source_id in "
                "(select id from sources where user_id=%(user_id)s)")
    cur = db.cursor()
    cur.execute(sql, {"group_id": group_id, "source_id": source_id,
                      "user_id": user_id})
    updated = cur.rowcount
    cur.close()
    return updated


_REFRESH_ERRORS_SQL = """
update source_state
set next_update=now()
where status='error'
    and source_id in (select id from sources where user_id=%s)
"""


def refresh_errors(db, user_id: int) -> int:
    """ Refresh all sources in error state for given user """
    cur = db.cursor()
    cur.execute(_REFRESH_ERRORS_SQL, (user_id, ))
    updated = cur.rowcount
    cur.close()
    return updated


def mark_read(db, source_id: int, max_id: int, min_id=0) -> int:
    """ Mark source read """
    cur = db.cursor()
    cur.execute(
        "update entries set read_mark=1 where source_id = %s "
        "and id <= %s and read_mark=0 and id >= %s",
        (source_id, max_id, min_id))
    changed = cur.rowcount
    cur.close()
    return changed


def get_filter_state(db, source_id: int, filter_name: str) \
        -> ty.Optional[ty.Dict[str, ty.Any]]:
    """ Get state for given filter in source """
    cur = db.cursor()
    cur.execute('select state from filters_state '
                'where source_id=%s and filter_name=%s',
                (source_id, filter_name))
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return json.loads(row[0]) if isinstance(row[0], str) and row[0] \
        else row[0]


def put_filter_state(db, source_id: int, filter_name: str, state):
    """ Save source filter state """
    cur = db.cursor()
    cur.execute(
        'delete from filters_state where source_id=%s and filter_name=%s',
        (source_id, filter_name))
    if state is not None:
        state = json.dumps(state)
        cur.execute(
            'insert into filter_name (source_id, filter_name, state) '
            'values(%s, %s, %s)', (source_id, filter_name, state))
    cur.close()


def _state_to_row(state: model.SourceState) -> ty.Dict[str, ty.Any]:
    return {
        "source_id": state.source_id,
        "next_update": state.next_update,
        "last_update": state.last_update,
        "last_error": state.last_error,
        "error_counter": state.error_counter,
        "success_counter": state.success_counter,
        "status": state.status,
        "error": state.error,
        "state": json.dumps(state.state),
    }


def _state_from_row(row) -> model.SourceState:
    state = model.SourceState()
    state.source_id = row["source_state_source_id"]
    state.next_update = row["source_state_next_update"]
    state.last_update = row["source_state_last_update"]
    state.last_error = row["source_state_last_error"]
    state.error_counter = row["source_state_error_counter"]
    state.success_counter = row["source_state_success_counter"]
    state.status = row["source_state_status"]
    state.error = row["source_state_error"]
    row_keys = row.keys()
    state.state = dbc.get_json_if_exists(row_keys, "source_state_state", row)
    return state
