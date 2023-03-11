#! /usr/bin/env python
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

from webmon2 import model

from . import _dbcommon as dbc
from . import binaries, groups
from ._db import DB

_ = ty
_LOG = logging.getLogger(__name__)


def get_names(
    db: DB, user_id: int, group_id: ty.Optional[int]
) -> list[tuple[int, str]]:
    """
    Get list of id, name all user sources optionally filtered by `group_id`
    and ordered by name;
    """
    _LOG.debug("get_names %r, %r", user_id, group_id)
    if not user_id:
        raise ValueError("missing user_id")

    with db.cursor() as cur:
        if group_id:
            cur.execute(
                "SELECT id, name FROM sources "
                "WHERE user_id=%s and group_id=%s ORDER BY name",
                (user_id, group_id),
            )
        else:
            cur.execute(
                "SELECT id, name FROM sources WHERE user_id=%s ORDER BY name",
                (user_id,),
            )

        return cur.fetchall()  # type: ignore


_GET_SOURCES_SQL = """
SELECT s.id AS source__id, s.group_id AS source__group_id,
    s.kind AS source__kind, s.name AS source__name,
    s.interval AS source__interval, s.settings AS source__settings,
    s.filters AS source__filters,
    s.user_id AS source__user_id,
    s.status AS source__status,
    s.mail_report AS source__mail_report,
    s.default_score AS source__default_score,
    ss.source_id AS source_state__source_id,
    ss.next_update AS source_state__next_update,
    ss.last_update AS source_state__last_update,
    ss.last_error AS source_state__last_error,
    ss.last_check AS source_state__last_check,
    ss.error_counter AS source_state__error_counter,
    ss.success_counter AS source_state__success_counter,
    ss.status AS source_state__status,
    ss.error AS source_state__error,
    ss.props AS source_state__props,
    ss.icon AS source_state__icon,
    (
        SELECT count(1)
        FROM entries
        WHERE source_id=s.id AND read_mark=0
    ) AS unread
FROM sources s
JOIN source_state ss ON ss.source_id = s.id
WHERE s.user_id=%(user_id)s"""


_ORDER_SQL_PART = {
    "name_desc": " ORDER BY s.name DESC",
    "update": " ORDER BY ss.last_update",
    "update_desc": " ORDER BY ss.last_update DESC",
    "next_update": " ORDER BY ss.next_update",
    "next_update_desc": " ORDER BY ss.next_update DESC",
}


def _get_order_sql(order: ty.Optional[str]) -> str:
    if not order:
        return " ORDER BY s.name"
    return _ORDER_SQL_PART.get(order, " ORDER BY s.name")


_STATUS_SQL_PART = {
    "disabled": " AND s.status = 2",
    "active": " AND s.status = 1",
    "notconf": " AND s.status = 0",
    "error": " AND ss.status = 'error' AND s.status = 1",
    "notupdated": " AND ss.last_update is null",
}


def _get_status_sql(status: ty.Optional[str]) -> str:
    if status:
        return _STATUS_SQL_PART.get(status, "")
    return ""


def get_all(
    db: DB,
    user_id: int,
    group_id: ty.Optional[int] = None,
    status: ty.Optional[str] = None,
    order: ty.Optional[str] = None,
) -> ty.Iterable[model.Source]:
    """Get all sources for given user and (optional) in group.
    Include state and number of unread entries.

    Args:
        db: database object
        user_id: user id
        group_id: optional group id to select sources
        status: optional status filter
        order: optional sorting
    """
    _LOG.debug("get_all (%r, %r, %r, %r)", user_id, group_id, status, order)
    if group_id:
        user_groups = {group_id: groups.get(db, group_id, user_id)}
    else:
        user_groups = {
            grp.id: grp for grp in groups.get_all(db, user_id)  # type: ignore
        }

    args = {"user_id": user_id, "group_id": group_id}
    sql = _GET_SOURCES_SQL
    if group_id is not None:
        sql += " and group_id = %(group_id)s"

    sql += _get_status_sql(status)
    sql += _get_order_sql(order)

    _LOG.debug("get_all %r %s", args, sql)
    with db.cursor() as cur:
        cur.execute(sql, args)
        return [_build_source(row, user_groups) for row in cur]


def get_all_dict(
    db: DB,
    user_id: int,
    group_id: ty.Optional[int] = None,
    status: ty.Optional[str] = None,
    order: ty.Optional[str] = None,
) -> dict[int, model.Source]:
    """Get all sources for given user and (optional) in group as dict
    source id -> source

    Args:
        db: database object
        user_id: user id
        group_id: optional group id to select sources
        status: optional status filter
        order: optional sorting
    """
    return {
        src.id: src for src in get_all(db, user_id, group_id, status, order)
    }


def _build_source(
    row: ty.Any, user_groups: dict[int, model.SourceGroup]
) -> model.Source:
    source = model.Source.from_row(row)
    source.state = model.SourceState.from_row(row)
    source.unread = row["unread"]
    group = user_groups[source.group_id]
    assert group
    source.group = group
    return source


_GET_SOURCE_SQL = """
SELECT id AS source__id, group_id AS source__group_id,
    kind AS source__kind, name AS source__name, interval AS source__interval,
    settings AS source__settings, filters AS source__filters,
    user_id AS source__user_id, status AS source__status,
    mail_report AS source__mail_report, default_score AS source__default_score
FROM sources
WHERE id=%s
"""


def get(
    db: DB,
    id_: int,
    with_state: bool = False,
    with_group: bool = True,
    user_id: ty.Optional[int] = None,
) -> model.Source:
    """Get one source with optionally with state and group info.
    Optionally check is source belong to given user.

    Args:
        db: database object
        id_: source id
        user_id: user id
        with_state: load source state
        with_group: load source group info
    """
    with db.cursor() as cur:
        cur.execute(_GET_SOURCE_SQL, (id_,))
        row = cur.fetchone()

    if row is None:
        raise dbc.NotFound()

    source = model.Source.from_row(row)
    if user_id and user_id != source.user_id:
        raise dbc.NotFound()

    if with_state:
        source.state = get_state(db, source.id)

    if with_group and source.group_id:
        source.group = groups.get(db, source.group_id, source.user_id)

    return source


_INSERT_SOURCE_SQL = """
INSERT INTO sources (group_id, kind, interval, settings, filters,
    user_id, name, status, mail_report, default_score)
VALUES (%(source__group_id)s, %(source__kind)s, %(source__interval)s,
    %(source__settings)s, %(source__filters)s, %(source__user_id)s,
    %(source__name)s, %(source__status)s, %(source__mail_report)s,
    %(source__default_score)s)
RETURNING id
"""

_UPDATE_SOURCE_SQL = """
UPDATE sources
SET group_id=%(source__group_id)s, kind=%(source__kind)s,
    name=%(source__name)s, interval=%(source__interval)s,
    settings=%(source__settings)s, filters=%(source__filters)s,
    status=%(source__status)s, mail_report=%(source__mail_report)s,
    default_score=%(source__default_score)s
WHERE id=%(source__id)s
"""


def save(db: DB, source: model.Source) -> model.Source:
    """Insert or update source.

    For new sources create & save SourceState object.

    Return:
        updates source
    """
    row = source.to_row()
    with db.cursor() as cur:
        if not source.id:
            cur.execute(_INSERT_SOURCE_SQL, row)
            res = cur.fetchone()
            assert res
            source.id = res[0]
            # create state for new source
            state = model.SourceState.new(source.id)
            state.status = model.SourceStateStatus.NEW
            save_state(db, state, source.user_id)
        else:
            cur.execute(_UPDATE_SOURCE_SQL, row)

    return source


def delete(db: DB, source_id: int) -> int:
    """Delete source.

    Return:
        number of deleted sources (should be 1)"""
    with db.cursor() as cur:
        cur.execute("delete from sources where id=%s", (source_id,))
        return cur.rowcount


def update_filter(
    db: DB, source_id: int, filter_idx: int, filter_: dict[str, ty.Any]
) -> None:
    """Append or update filter in given source.

    Args:
        db: database object
        source_id: source id
        filter_idx: filter index to update
        filter_: filter configuration
    """
    try:
        source = get(db, source_id, with_group=False)
    except dbc.NotFound:
        _LOG.warning("update_filter: source %d not found", source_id)
        return

    if not source.filters:
        source.filters = [filter_]
    elif 0 <= filter_idx < len(source.filters):
        source.filters[filter_idx] = filter_
    else:
        source.filters.append(filter_)

    save(db, source)


def delete_filter(
    db: DB, user_id: int, source_id: int, filter_idx: int
) -> None:
    """Delete filter in source

    Args:
        db: database object
        user_id: user id for sanity check
        source_id: source id
        filter_idx: filter index to delete

    """
    source = get(db, source_id, with_group=False)
    if not source or source.user_id != user_id:
        _LOG.warning("invalid source (%r, %r) %r", user_id, source_id, source)
        return

    if source.filters and filter_idx < len(source.filters):
        del source.filters[filter_idx]
        save(db, source)
    else:
        _LOG.warning("invalid filter index %r in %r", filter_idx, source)


def move_filter(
    db: DB, user_id: int, source_id: int, filter_idx: int, direction: str
) -> None:
    """Change position of given filter in source

    Args:
        db: database object
        user_id: user id for sanity check
        source_id: source id
        filter_idx: filter index to delete
        direction: "up" or "down"

    """
    if direction not in ("up", "down"):
        raise ValueError("invalid direction")

    source = get(db, source_id, with_group=False)
    if not source or source.user_id != user_id:
        return

    if (
        not source.filters
        or filter_idx >= len(source.filters)
        or len(source.filters) == 1
    ):
        return

    if direction == "up":
        if filter_idx <= 0:
            return

        source.filters[filter_idx - 1], source.filters[filter_idx] = (
            source.filters[filter_idx],
            source.filters[filter_idx - 1],
        )
        save(db, source)
    elif direction == "down":
        if filter_idx >= len(source.filters) - 2:
            return

        source.filters[filter_idx + 1], source.filters[filter_idx] = (
            source.filters[filter_idx],
            source.filters[filter_idx + 1],
        )
        save(db, source)


_GET_STATE_SQL = """
SELECT source_id AS source_state__source_id,
    next_update AS source_state__next_update,
    last_update AS source_state__last_update,
    last_check AS source_state__last_check,
    last_error AS source_state__last_error,
    error_counter AS source_state__error_counter,
    success_counter AS source_state__success_counter,
    status AS source_state__status,
    error AS source_state__error,
    props AS source_state__props,
    icon AS source_state__icon
FROM source_state
WHERE source_id=%s
"""


def get_state(db: DB, source_id: int) -> ty.Optional[model.SourceState]:
    """Get state for given source"""
    with db.cursor() as cur:
        cur.execute(_GET_STATE_SQL, (source_id,))
        row = cur.fetchone()

    return model.SourceState.from_row(row) if row else None


_INSERT_STATE_SQL = """
INSERT INTO source_state(source_id, next_update, last_update, last_error,
    error_counter, success_counter, status, error, props, icon, last_check)
VALUES (%(source_state__source_id)s, %(source_state__next_update)s,
    %(source_state__last_update)s, %(source_state__last_error)s,
    %(source_state__error_counter)s, %(source_state__success_counter)s,
    %(source_state__status)s, %(source_state__error)s, %(source_state__props)s,
    %(source_state__icon)s, %(source_state__last_check)s)
"""

_UPDATE_STATE_SQL = """
UPDATE source_state
SET next_update=%(source_state__next_update)s,
    last_update=%(source_state__last_update)s,
    last_error=%(source_state__last_error)s,
    last_check=%(source_state__last_check)s,
    error_counter=%(source_state__error_counter)s,
    success_counter=%(source_state__success_counter)s,
    status=%(source_state__status)s,
    error=%(source_state__error)s,
    props=%(source_state__props)s,
    icon=%(source_state__icon)s
WHERE source_id=%(source_state__source_id)s
"""


def save_state(
    db: DB, state: model.SourceState, user_id: int
) -> model.SourceState:
    """Save (replace) source state and binaries if set"""
    _LOG.debug("save_state: %s", state)
    row = model.SourceState.to_row(state)
    with db.cursor() as cur:
        cur.execute(
            "delete from source_state where source_id=%s", (state.source_id,)
        )
        cur.execute(_INSERT_STATE_SQL, row)

    if state.icon_data and state.icon:
        content_type, data = state.icon_data
        binaries.save(db, user_id, content_type, state.icon, data)

    return state


_GET_SOURCES_TO_FETCH_SQL = f"""
SELECT s.id
FROM source_state ss
JOIN sources s ON s.id = ss.source_id
JOIN users u ON s.user_id = u.id
WHERE ss.next_update <= now()
    AND s.status = {model.SourceStatus.ACTIVE}
    AND u.active
"""


def get_sources_to_fetch(db: DB) -> list[int]:
    """Find sources with next update state in past"""
    with db.cursor() as cur:
        cur.execute(_GET_SOURCES_TO_FETCH_SQL)
        return [row[0] for row in cur]


_REFRESH_SQL = """
UPDATE source_state
SET next_update=now()
WHERE (last_update IS NULL
        OR last_update < now() - '-1 minutes'::interval
    )
    AND source_id IN (
        SELECT id FROM sources
        WHERE user_id=%(user_id)s
            AND status=%(active)s
    )
"""


def refresh(
    db: DB,
    user_id: int,
    source_id: ty.Optional[int] = None,
    group_id: ty.Optional[int] = None,
) -> int:
    """Mark source to refresh; return founded sources"""
    if not (user_id or source_id or group_id):
        raise ValueError("missing user_id/source_id/group_id")

    sql = _REFRESH_SQL
    if group_id:
        sql += (
            "and source_id in "
            "(select id from sources where group_id=%(group_id)s)"
        )
    elif source_id:
        sql += "and source_id=%(source_id)s"

    with db.cursor() as cur:
        cur.execute(
            sql,
            {
                "group_id": group_id,
                "source_id": source_id,
                "user_id": user_id,
                "active": model.SourceStatus.ACTIVE,
            },
        )
        updated = cur.rowcount

    return updated


_REFRESH_ERRORS_SQL = """
UPDATE source_state
SET next_update=now()
WHERE status='error'
    AND source_id IN (
        SELECT id FROM sources WHERE user_id=%s AND status=%s
    )
"""


def refresh_errors(db: DB, user_id: int) -> int:
    """Refresh all sources in error state for given user"""
    with db.cursor() as cur:
        cur.execute(_REFRESH_ERRORS_SQL, (user_id, model.SourceStatus.ACTIVE))
        return cur.rowcount


_MARK_READ_SQL = """
UPDATE entries
SET read_mark=%(read_mark)s
WHERE source_id=%(source_id)s
    AND (id<=%(max_id)s OR %(max_id)s<0) AND id>=%(min_id)s
    AND read_mark=%(unread)s AND user_id=%(user_id)s
"""

_MARK_READ_BY_IDS_SQL = """
UPDATE entries
SET read_mark=%(read_mark)s
WHERE source_id=%(source_id)s
    AND id=ANY(%(ids)s)
    AND read_mark=%(unread)s AND user_id=%(user_id)s
"""


# pylint: disable=too-many-arguments
def mark_read(
    db: DB,
    user_id: int,
    source_id: int,
    max_id: ty.Optional[int] = None,
    min_id: ty.Optional[int] = None,
    ids: ty.Optional[ty.Iterable[int]] = None,
) -> int:
    """Mark source read"""
    args = {
        "source_id": source_id,
        "max_id": max_id,
        "min_id": min_id,
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

        return cur.rowcount


def get_filter_state(
    db: DB, source_id: int, filter_name: str
) -> ty.Optional[dict[str, ty.Any]]:
    """Get state for given filter in source"""
    with db.cursor() as cur:
        cur.execute(
            "SELECT state "
            "FROM filters_state "
            "WHERE source_id=%s AND filter_name=%s",
            (source_id, filter_name),
        )
        row = cur.fetchone()

    if not row:
        return None

    if isinstance(row[0], str) and row[0]:
        return json.loads(row[0])  # type: ignore

    return None


def put_filter_state(
    db: DB, source_id: int, filter_name: str, state: dict[str, ty.Any]
) -> None:
    """Save source filter state"""
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM filters_state "
            "WHERE source_id=%s AND filter_name=%s",
            (source_id, filter_name),
        )
        if state is not None:
            s_state = json.dumps(state)
            cur.execute(
                "INSERT INTO filters_state (source_id, filter_name, state) "
                "VALUES(%s, %s, %s)",
                (source_id, filter_name, s_state),
            )


def find_next_entry_id(
    db: DB, source_id: int, entry_id: int, unread: bool = True
) -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "SELECT min(e.id) "
                "FROM entries e "
                "WHERE e.id > %s AND e.read_mark=%s AND e.source_id=%s",
                (entry_id, model.EntryReadMark.UNREAD, source_id),
            )
        else:
            cur.execute(
                "SELECT min(e.id) "
                "FROM entries e  "
                "WHERE e.id > %s AND e.source_id=%s",
                (entry_id, source_id),
            )

        row = cur.fetchone()
        return row[0] if row else None


def find_prev_entry_id(
    db: DB, source_id: int, entry_id: int, unread: bool = True
) -> ty.Optional[int]:
    with db.cursor() as cur:
        if unread:
            cur.execute(
                "SELECT max(e.id) "
                "FROM entries e "
                "WHERE e.id < %s AND e.read_mark=%s AND e.source_id=%s",
                (entry_id, model.EntryReadMark.UNREAD, source_id),
            )
        else:
            cur.execute(
                "SELECT max(e.id) "
                "FROM entries e "
                "WHERE e.id < %s AND e.source_id=%s",
                (entry_id, source_id),
            )

        row = cur.fetchone()
        return row[0] if row else None


def find_next_unread(db: DB, user_id: int) -> ty.Optional[int]:
    with db.cursor() as cur:
        cur.execute(
            "SELECT e.source_id "
            "FROM entries e "
            "WHERE e.user_id = %s AND e.read_mark=%s",
            (user_id, model.EntryReadMark.UNREAD),
        )
        row = cur.fetchone()
        return row[0] if row else None


_RANDOMIZE_NEXT_CHECK_SQL = f"""
UPDATE source_state
SET next_update = next_update + (random() * 180) * interval '1 minute'
WHERE source_id IN (
    SELECT id
    FROM sources
    WHERE user_id = %s
      AND status = {model.SourceStatus.ACTIVE}
)
"""


def randomize_next_check(db: DB, user_id: int) -> int:
    """Add random (0-60minutes) to next check for all user sources."""
    with db.cursor() as cur:
        cur.execute(_RANDOMIZE_NEXT_CHECK_SQL, (user_id,))
        return cur.rowcount
