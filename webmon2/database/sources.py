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
import logging
import typing as ty
import datetime

from webmon2 import model
from . import _dbcommon as dbc
from . import groups, binaries

_ = ty
_LOG = logging.getLogger(__name__)

_GET_SOURCES_SQL_BASE = """
select s.id as source__id, s.group_id as source__group_id,
    s.kind as source__kind, s.name as source__name,
    s.interval as source__interval, s.settings as source__settings,
    s.filters as source__filters,
    s.user_id as source__user_id,
    s.status as source__status,
    s.mail_report as source__mail_report,
    ss.source_id as source_state__source_id,
    ss.next_update as source_state__next_update,
    ss.last_update as source_state__last_update,
    ss.last_error as source_state__last_error,
    ss.error_counter as source_state__error_counter,
    ss.success_counter as source_state__success_counter,
    ss.status as source_state__status,
    ss.error as source_state__error,
    ss.state as source_state__state,
    ss.icon as source_state__icon,
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
    with db.cursor() as cur:
        user_groups = {g.id: g for g in groups.get_all(db, user_id)}
        args = {"user_id": user_id, "group_id": group_id}
        sql = _GET_SOURCES_SQL if group_id is None \
            else _GET_SOURCES_BY_GROUP_SQL
        cur.execute(sql, args)
        for row in cur:
            source = model.Source.from_row(row)
            source.state = model.SourceState.from_row(row)
            source.unread = row['unread']
            source.group = user_groups.get(source.group_id) \
                if source.group_id else None
            yield source


_GET_SOURCE_SQL = """
select id as source__id, group_id as source__group_id,
    kind as source__kind, name as source__name, interval as source__interval,
    settings as source__settings, filters as source__filters,
    user_id as source__user_id, status as source__status,
    mail_report as source__mail_report
from sources where id=%s
"""


def get(db, id_: int, with_state=False, with_group=True) -> model.Source:
    """ Get one source with optionally with state and group info """
    with db.cursor() as cur:
        cur.execute(_GET_SOURCE_SQL, (id_, ))
        row = cur.fetchone()

    if row is None:
        raise dbc.NotFound()

    source = model.Source.from_row(row)
    if with_state:
        source.state = get_state(db, source.id)
    if with_group and source.group_id:
        source.group = groups.get(db, source.group_id)

    return source


_INSERT_SOURCE_SQL = """
insert into sources (group_id, kind, interval, settings, filters,
    user_id, name, status, mail_report)
    values (%(source__group_id)s, %(source__kind)s, %(source__interval)s,
        %(source__settings)s, %(source__filters)s, %(source__user_id)s,
        %(source__name)s, %(source__status)s, %(source__mail_report)s)
returning id
"""

_UPDATE_SOURCE_SQL = """
update sources
set group_id=%(source__group_id)s, kind=%(source__kind)s,
    name=%(source__name)s, interval=%(source__interval)s,
    settings=%(source__settings)s, filters=%(source__filters)s,
    status=%(source__status)s, mail_report=%(source__mail_report)s
where id=%(source__id)s
"""


def save(db, source: model.Source) -> model.Source:
    """ Insert or update source """
    row = source.to_row()
    with db.cursor() as cur:
        if source.id is None:
            cur.execute(_INSERT_SOURCE_SQL, row)
            source.id = cur.fetchone()[0]
            # create state for new source
            state = model.SourceState.new(source.id)
            save_state(db, state, source.user_id)
        else:
            cur.execute(_UPDATE_SOURCE_SQL, row)
    return source


def delete(db, source_id: int) -> int:
    """ Delete source """
    with db.cursor() as cur:
        cur.execute("delete from sources where id=%s", (source_id, ))
        updated = cur.rowcount
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


def delete_filter(db, user_id: int, source_id: int, filter_idx: int):
    """ Delete filter in source """
    source = get(db, source_id, False, False)
    if not source or source.user_id != user_id:
        return
    if source.filters and filter_idx < len(source.filters):
        del source.filters[filter_idx]
        save(db, source)


def move_filter(db, user_id: int, source_id: int, filter_idx: int,
                direction: str):
    """ Change position of given filter in source """
    assert direction in ('up', 'down')
    source = get(db, source_id, False, False)
    if not source or source.user_id != user_id:
        return
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
select source_id as source_state__source_id,
    next_update as source_state__next_update,
    last_update as source_state__last_update,
    last_error as source_state__last_error,
    error_counter as source_state__error_counter,
    success_counter as source_state__success_counter,
    status as source_state__status,
    error as source_state__error,
    state as source_state__state,
    icon as source_state__icon
from source_state where source_id=%s
"""


def get_state(db, source_id: int) -> ty.Optional[model.SourceState]:
    """ Get state for given source """
    cur = db.cursor()
    cur.execute(_GET_STATE_SQL, (source_id, ))
    row = cur.fetchone()
    state = model.SourceState.from_row(row) if row else None
    cur.close()
    return state


_INSERT_STATE_SQL = """
insert into source_state(source_id, next_update, last_update, last_error,
    error_counter, success_counter, status, error, state, icon)
values (%(source_state__source_id)s, %(source_state__next_update)s,
    %(source_state__last_update)s, %(source_state__last_error)s,
    %(source_state__error_counter)s, %(source_state__success_counter)s,
    %(source_state__status)s, %(source_state__error)s, %(source_state__state)s,
    %(source_state__icon)s)
"""

_UPDATE_STATE_SQL = """
update source_state
set  next_update=%(source_state__next_update)s,
     last_update=%(source_state__last_update)s,
     last_error=%(source_state__last_error)s,
     error_counter=%(source_state__error_counter)s,
     success_counter=%(source_state__success_counter)s,
     status=%(source_state__status)s,
     error=%(source_state__error)s,
     state=%(source_state__state)s,
     icon=%(source_state__icon)s
where source_id=%(source_state__source_id)s
"""


def save_state(db, state: model.SourceState, user_id: int) \
        -> model.SourceState:
    """ Save (replace) source state """
    row = model.SourceState.to_row(state)
    with db.cursor() as cur:
        cur.execute("delete from source_state where source_id=%s",
                    (state.source_id,))
        cur.execute(_INSERT_STATE_SQL, row)
    if state.icon_data:
        content_type, data = state.icon_data
        binaries.save(db, user_id, content_type, state.icon, data)
    return state


_GET_SOURCES_TO_FETCH_SQL = """
    select ss.source_id
    from source_state  ss
    join sources s on s.id = ss.source_id
    where ss.next_update <= %s
        and s.status = 1
"""


def get_sources_to_fetch(db) -> ty.List[int]:
    """ Find sources with next update state in past """
    with db.cursor() as cur:
        cur.execute(_GET_SOURCES_TO_FETCH_SQL, (datetime.datetime.now(), ))
        ids = [row[0] for row in cur]
        return ids


_REFRESH_SQL = """
update source_state
set next_update=now()
where (last_update is null or last_update < now() - '-1 minutes'::interval)
    and source_id in (
        select id from sources
        where user_id=%(user_id)s
            and status=1
    )
"""


def refresh(db, user_id, source_id=None, group_id=None) -> int:
    """ Mark source to refresh; return founded sources """
    assert user_id or source_id or group_id
    sql = _REFRESH_SQL
    if group_id:
        sql += ("and source_id in "
                "(select id from sources where group_id=%(group_id)s)")
    elif source_id:
        sql += "and source_id=%(source_id)s"
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
    and source_id in (
        select id from sources where user_id=%s and status=1
    )
"""


def refresh_errors(db, user_id: int) -> int:
    """ Refresh all sources in error state for given user """
    with db.cursor() as cur:
        cur.execute(_REFRESH_ERRORS_SQL, (user_id, ))
        updated = cur.rowcount
        return updated


_MARK_READ_SQL = """
update entries
set read_mark=1
where source_id=%(source_id)s
    and (id<=%(max_id)s or %(max_id)s<0) and id>=%(min_id)s
    and read_mark=0 and user_id=%(user_id)s
"""


def mark_read(db, user_id: int, source_id: int, max_id: int, min_id=0) -> int:
    """ Mark source read """
    with db.cursor() as cur:
        cur.execute(
            _MARK_READ_SQL,
            {'source_id': source_id, 'max_id': max_id, 'min_id': min_id,
             'user_id': user_id})
        changed = cur.rowcount
        return changed


def get_filter_state(db, source_id: int, filter_name: str) \
        -> ty.Optional[ty.Dict[str, ty.Any]]:
    """ Get state for given filter in source """
    with db.cursor() as cur:
        cur.execute('select state from filters_state '
                    'where source_id=%s and filter_name=%s',
                    (source_id, filter_name))
        row = cur.fetchone()
    if not row:
        return None
    return json.loads(row[0]) if isinstance(row[0], str) and row[0] \
        else row[0]


def put_filter_state(db, source_id: int, filter_name: str, state):
    """ Save source filter state """
    with db.cursor() as cur:
        cur.execute(
            'delete from filters_state '
            'where source_id=%s and filter_name=%s',
            (source_id, filter_name))
        if state is not None:
            state = json.dumps(state)
            cur.execute(
                'insert into filters_state (source_id, filter_name, state) '
                'values(%s, %s, %s)', (source_id, filter_name, state))


def find_next_entry_id(db, source_id: int, entry_id: int, unread=True) \
        -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "select min(e.id) "
                "from entries e "
                "where e.id > %s and e.read_mark=0 and e.source_id=%s",
                (entry_id, source_id))
        else:
            cur.execute(
                "select min(e.id) "
                "from entries e  "
                "where e.id > %s and e.source_id=%s",
                (entry_id, source_id))
        row = cur.fetchone()
        return row[0] if row else None


def find_prev_entry_id(db, source_id: int, entry_id: int, unread=True) \
        -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "select max(e.id) "
                "from entries e "
                "where e.id < %s and e.read_mark=0 and e.source_id=%s",
                (entry_id, source_id))
        else:
            cur.execute(
                "select max(e.id) "
                "from entries e "
                "where e.id < %s and e.source_id=%s",
                (entry_id, source_id))
        row = cur.fetchone()
        return row[0] if row else None


def find_next_unread(db, user_id: int) -> ty.Optional[int]:
    with db.cursor() as cur:
        cur.execute(
            "select e.source_id "
            "from entries e "
            "where e.user_id = %s and e.read_mark=0",
            (user_id, ))
        row = cur.fetchone()
        return row[0] if row else None
