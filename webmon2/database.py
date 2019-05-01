#!/usr/bin/python3
"""
Cache storage functions.

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""
import logging
import os.path
import sqlite3
import json
import typing as ty

from . import common, model

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"

_LOG = logging.getLogger("db")


class NotFound(Exception):
    pass


class DB:

    INSTANCE = None

    def __init__(self, filename: str) -> None:
        super().__init__()
        self._filename = filename
        self._conn = sqlite3.connect(self._filename, timeout=10,
                                     isolation_level="EXCLUSIVE",
                                     detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("PRAGMA journal_mode=WAL;"
                                 "PRAGMA foreign_keys = ON;")

    def clone(self):
        return DB(self._filename)

    @classmethod
    def get(cls):
        return cls.INSTANCE.clone()

    @classmethod
    def initialize(cls, filename):
        _LOG.info("initializing database: %s", filename)
        common.create_missing_dir(os.path.dirname(filename))
        db = DB(filename)
        db.update_schema()
        db.close()
        cls.INSTANCE = db
        return db

    def __enter__(self):
        return self

    def __exit__(self, type_, value, traceback):
        self.close()
        return isinstance(value, TypeError)

    def close(self):
        if self._conn is not None:
            self._conn.executescript("PRAGMA optimize")
            self._conn.close()
            self._conn = None

    def get_groups(self, user_id):
        assert user_id
        cur = self._conn.cursor()
        cur.execute(_GET_SOURCE_GROUPS_SQL, (user_id, ))
        groups = [model.SourceGroup(id, name, unread, user_id)
                  for id, name, user_id, unread in cur]
        return groups

    def get_group(self, id_):
        cur = self._conn.cursor()
        cur.execute(
            "select id as source_group_id, name as source_group_name, "
            "user_id as source_group_user_id from source_groups where id=?",
            (id_, ))
        row = cur.fetchone()
        if not row:
            raise NotFound
        return _source_group_from_row(row)

    def save_group(self, group):
        cur = self._conn.cursor()
        if group.id is None:
            cur.execute(
                "insert into source_groups (name, user_id) values (?, ?)",
                (group.name, group.user_id))
            group.id = cur.lastrowid
        else:
            cur.execute("update source_groups set name=? where id=?",
                        (group.name, group.id))
        self._conn.commit()
        return group

    def get_next_unread_group(self, user_id):
        cur = self._conn.cursor()
        cur.execute(
            "select group_id "
            "from sources s join entries e on e.source_id = s.id "
            "where e.read_mark = 0 and s.user_id=? "
            "order by e.id limit 1", (user_id, ))
        row = cur.fetchone()
        return row[0] if row else None

    def get_sources(self, user_id, group_id=None):
        cur = self._conn.cursor()
        groups = {g.id: g for g in self.get_groups(user_id)}
        if group_id is None:
            cur.execute(_GET_SOURCES_SQL, (user_id, ))
        else:
            cur.execute(_GET_SOURCES_BY_GROUP_SQL, (group_id, user_id))
        for row in cur:
            source = _source_from_row(row)
            source.state = _state_from_row(row)
            source.unread = row['unread']
            source.group = groups.get(source.group_id) if source.group_id \
                else None
            yield source

    def get_source(self, id_, with_state=False, with_group=True):
        cur = self._conn.cursor()
        cur.execute(_GET_SOURCE_SQL, (id_, ))
        row = cur.fetchone()
        if row is None:
            raise NotFound()

        source = _source_from_row(row)
        if with_state:
            source.state = self.get_state(source.id)
        if with_group and source.group_id:
            source.group = self.get_group(source.group_id)

        return source

    def save_source(self, source):
        cur = self._conn.cursor()
        row = _source_to_row(source)
        if source.id is None:
            cur.execute(_INSERT_SOURCE_SQL, row)
            source.id = cur.lastrowid
            state = model.SourceState.new(source.id)
            self.save_state(state)
        else:
            cur.execute(_UPDATE_SOURCE_SQL, row)
        self._conn.commit()
        return source

    def source_delete(self, source_id: int) -> int:
        cur = self._conn.cursor()
        cur.execute("delete from sources where id=?", (source_id, ))
        updated = cur.rowcount
        self._conn.commit()
        return updated

    def source_update_filter(self, source_id: int, filter_idx: int,
                             filter_: ty.Dict[str, ty.Any]):
        source = self.get_source(source_id, False, False)
        if not source.filters:
            source.filters = [filter_]
        elif 0 <= filter_idx < len(source.filters):
            source.filters[filter_idx] = filter_
        else:
            source.filters.append(filter_)
        self.save_source(source)

    def source_delete_filter(self, source_id: int, filter_idx: int):
        source = self.get_source(source_id, False, False)
        if source.filters and filter_idx < len(source.filters):
            del source.filters[filter_idx]
            self.save_source(source)

    def source_move_filter(self, source_id: int, filter_idx: int,
                           direction: str):
        source = self.get_source(source_id, False, False)
        if not source.filters or filter_idx >= len(source.filters) \
                or len(source.filters) == 1:
            return
        if direction == 'up' and filter_idx > 0:
            source.filters[filter_idx - 1], source.filters[filter_idx] = \
                source.filters[filter_idx], source.filters[filter_idx - 1]
            self.save_source(source)

        if direction == 'down' and filter_idx < len(source.filters) - 2:
            source.filters[filter_idx + 1], source.filters[filter_idx] = \
                source.filters[filter_idx], source.filters[filter_idx + 1]
            self.save_source(source)

    def refresh(self, source_id=None, group_id=None):
        cur = self._conn.cursor()
        args = {"group_id": group_id, "source_id": source_id}
        sql = ["update source_state "
               "set next_update=datetime('now', 'localtime') "
               "where (last_update is null or "
               "last_update < datetime('now', 'localtime', '-15 minutes'))"]
        if group_id:
            sql.append(
                "and source_id in "
                "(select id from sources where group_id=:group_id)")
        elif source_id:
            sql.append("and source_id=:source_id")
        cur.execute(" ".join(sql), args)
        updated = cur.rowcount
        self._conn.commit()
        return updated

    def refresh_errors(self):
        cur = self._conn.cursor()
        cur.execute("update source_state set next_update=datetime('now') "
                    "where status='error'")
        updated = cur.rowcount
        self._conn.commit()
        return updated

    def get_state(self, source_id):
        cur = self._conn.cursor()
        cur.execute(_GET_STATE_SQL, (source_id, ))
        row = cur.fetchone()
        return _state_from_row(row) if row else None

    def save_state(self, state):
        cur = self._conn.cursor()
        row = _state_to_row(state)
        cur.execute("delete from source_state where source_id=?",
                    (state.source_id,))
        cur.execute(_INSERT_STATE_SQL, row)
        self._conn.commit()
        return state

    def get_sources_to_fetch(self):
        cur = self._conn.cursor()
        ids = [row[0] for row in
               cur.execute(
                   """select source_id from source_state
                      where next_update <= datetime('now', 'localtime')""")
               ]
        return ids

    def get_starred_entries(self, user_id: int):
        assert user_id, 'no user_id'
        cur = self._conn.cursor()
        for row in cur.execute(_GET_STARRED_ENTRIES_SQL, {'user_id': user_id}):
            entry = _entry_from_row(row)
            entry.source = _source_from_row(row)
            if entry.source.group_id:
                entry.source.group = _source_group_from_row(row)
            yield entry

    def get_entries_total_count(self, user_id, source_id=None, group_id=None,
                                unread=True) -> int:
        cur = self._conn.cursor()
        args = {
            'group_id': group_id,
            'source_id': source_id,
            "user_id": user_id,
        }
        sql = _get_entries_get_sql(source_id, group_id, unread)
        sql = "select count(*) from (" + sql + ")"
        cur.execute(sql, args)
        return cur.fetchone()[0]

    def get_entries(self, user_id, source_id=None, group_id=None, unread=True,
                    offset=None, limit=None):
        cur = self._conn.cursor()
        args = {
            'limit': limit or 25,
            'offset': offset or 0,
            'group_id': group_id,
            'source_id': source_id,
            "user_id": user_id,
        }
        sql = _get_entries_get_sql(source_id, group_id, unread)
        if not unread:
            # for unread there is no pagination
            sql += " limit :limit offset :offset"
        _LOG.debug("sql: %r", sql)
        _LOG.debug("args: %r", args)
        cur.execute(sql, args)
        groups = {}
        for row in cur:
            entry = _entry_from_row(row)
            entry.source = _source_from_row(row)
            if entry.source.group_id:
                group = groups.get(entry.source.group_id)
                if not group:
                    group = groups[entry.source.group_id] = \
                        _source_group_from_row(row)
                entry.source.group = group
            _LOG.debug("entry %s", entry)
            yield entry

    def get_entry(self, id_=None, oid=None):
        assert id_ is not None or oid is not None
        cur = self._conn.cursor()
        if id_ is not None:
            cur.execute(_GET_ENTRY_BY_ID_SQL, (id_, ))
        else:
            cur.execute(_GET_ENTRY_BY_OID_SQL, (oid, ))
        row = cur.fetchone()
        if not row:
            raise NotFound()
        return _entry_from_row(row)

    def save_entry(self, entry):
        row = _entry_to_row(entry)
        cur = self._conn.cursor()
        if entry.id is None:
            cur.execute(_INSERT_ENTRY_SQL, row)
            entry.id = cur.lastrowid
        else:
            cur.execute(_UPDATE_ENTRY_SQL, row)
        self._conn.commit()
        return entry

    def insert_entries(self, entries):
        _LOG.debug("total entries: %d", len(entries))
        # since sqlite in this version not support upsert, simple check, remve
        cur = self._conn.cursor()
        # filter updated entries; should be deleted & inserted
        oids_to_delete = [(entry.oid, ) for entry in entries
                          if entry.status == 'updated']
        _LOG.debug("delete oids: %d", len(oids_to_delete))
        cur.executemany("delete from entries where oid=?", oids_to_delete)
        rows = [
            _entry_to_row(entry)
            for entry in entries
            if entry.status == 'updated' or
            cur.execute(_CHECK_ENTRY_SQL,
                        (entry.oid, entry.user_id)).fetchone() is None
        ]
        _LOG.debug("new entries: %d", len(rows))
        cur.executemany(_INSERT_ENTRY_SQL, rows)
        self._conn.commit()

    def delete_old_entries(self, user_id: int, max_datetime):
        cur = self._conn.cursor()
        cur.execute("delete from entries where star_mark=0 and read_mark=0 "
                    "and updated<? and user_id=?", (max_datetime, user_id))
        deleted = cur.rowcount
        _LOG.info("delete_old_entries; user: %d, deleted: %d", user_id,
                  deleted)
        self._conn.commit()

    def mark_read(self, user_id: int, entry_id=None, min_id=None, max_id=None,
                  read=True):
        assert user_id and (entry_id or max_id)
        read = 1 if read else 0
        _LOG.info("mark_read entry_id=%r, min_id=%r, max_id=%r, read=%r, "
                  "user_id=%r", entry_id, min_id, max_id, read, user_id)
        cur = self._conn.cursor()
        if entry_id:
            cur.execute(
                "update entries set read_mark=? where id = ? "
                "and read_mark = ? and user_id=?",
                (read, entry_id, 1-read, user_id))
        elif max_id:
            cur.execute(
                "update entries set read_mark=? where id <= ? and id >= ? "
                "and user_id=?", (read, max_id, min_id or 0, user_id))
        changed = cur.rowcount
        _LOG.debug("total changes: %d, changed: %d", self._conn.total_changes,
                   changed)
        self._conn.commit()
        return changed

    def group_mark_read(self, group_id, min_id=None, max_id=None, read=True):
        assert group_id, "no group id"
        read = 1 if read else 0
        _LOG.info("group_mark_read group_id=%r,max_id=%r, read=%r",
                  group_id, max_id, read)
        cur = self._conn.cursor()
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
        _LOG.debug("total changes: %d, changed: %d", self._conn.total_changes,
                   changed)
        self._conn.commit()
        return changed

    def source_mark_read(self, source_id=None, min_id=None, max_id=None,
                         read=True):
        read = 1 if read else 0
        _LOG.info("source_mark_read source_id=%r, max_id=%r, read=%r",
                  source_id, max_id, read)
        cur = self._conn.cursor()
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
        _LOG.debug("total changes: %d, changed: %d", self._conn.total_changes,
                   changed)
        self._conn.commit()
        return changed

    def mark_star(self, entry_id=None, star=True):
        star = 1 if star else 0
        _LOG.info("mark_star entry_id=%r,star=%r", entry_id, star)
        cur = self._conn.cursor()
        cur.execute(
            "update entries set star_mark=? where id = ? and star_mark = ?",
            (star, entry_id, 1-star))
        changed = cur.rowcount
        _LOG.debug("total changes: %d, changed: %d", self._conn.total_changes,
                   changed)
        self._conn.commit()
        return changed

    def check_entry_oids(self, oids, source_id):
        assert source_id
        cur = self._conn.cursor()
        result = set()
        for idx in range(0, len(oids), 100):
            part_oids = oids[idx:idx+100]
            part_oids = ", ".join("'" + oid + "'" for oid in part_oids)
            cur.execute(
                "select oid from history_oids where source_id=? and oid in ("
                + part_oids + ")", (source_id, ))
            result.update({row[0] for row in cur})
        new_oids = [oid for oid in oids if oid not in result]
        cur.executemany(
            "insert into history_oids(source_id, oid) values (?, ?)",
            [(source_id, oid) for oid in new_oids])
        self._conn.commit()
        return result

    def get_settings(self, user_id) -> ty.Iterable[model.Setting]:
        cur = self._conn.cursor()
        if user_id is None:
            cur.execute(
                "select key, value, value_type, description from settings")
        else:
            cur.execute(
                "select key, value, value_type, description from settings "
                "where user_id=?", (user_id, ))
        for row in cur:
            yield _setting_from_row(row)

    def get_setting(self, key: str, user_id: int) \
            -> ty.Optional[model.Setting]:
        cur = self._conn.cursor()
        cur.execute("select key, value, value_type, description "
                    "from settings where key=? and user_id=?",
                    (key, user_id))
        row = cur.fetchone()
        return _setting_from_row(row) if row else None

    def save_setting(self, setting: model.Setting):
        cur = self._conn.cursor()
        cur.execute("update settings set value=? where key=? and user_id=?",
                    (setting.key, json.dumps(setting.value), setting.user_id))
        self._conn.commit()

    def save_settings(self, settings: ty.List[model.Setting]):
        cur = self._conn.cursor()
        rows = [(json.dumps(setting.value), setting.key, setting.user_id)
                for setting in settings]
        cur.executemany(
            "update settings set value=? where key=? and user_id=?", rows)
        self._conn.commit()

    def get_setting_value(self, key: str, user_id: int, default=None) \
            -> ty.Any:
        cur = self._conn.cursor()
        cur.execute("select value from settings where key=? and user_id=?",
                    (key, user_id))
        row = cur.fetchone()
        if row is None or row[0] is None:
            return default
        return json.loads(row[0]) if isinstance(row[0], str) else row[0]

    def get_settings_map(self, user_id: int) -> ty.Dict[str, ty.Any]:
        return {key: json.loads(val) if isinstance(val, str) and val else val
                for key, val
                in self._conn.execute(
                    "select key, value from settings where user_id=?",
                    (user_id, ))}

    def get_users(self) -> ty.Iterable[model.User]:
        cur = self._conn.cursor()
        for row in cur.execute(
                "select id, login, email, password, active, admin from users"):
            yield _user_from_row(row)

    def get_user(self, id_=None, login=None) -> ty.Optional[model.User]:
        cur = self._conn.cursor()
        if id_:
            cur.execute("select id, login, email, password, active, admin "
                        "from users where id=?", (id_, ))
        elif login:
            cur.execute("select id, login, email, password, active, admin "
                        "from users where login=?", (login, ))
        else:
            return None
        row = cur.fetchone()
        if not row:
            return None
        user = _user_from_row(row)
        return user

    def save_user(self, user: model.User) -> ty.Optional[model.User]:
        cur = self._conn.cursor()
        if user.id:
            cur.execute(
                "update users set login=:login, email=:email, "
                "password=:password, active=:active, admin=admin "
                "where id=:id",
                _user_to_row(user))
        else:
            cur.execute("select 1 from users where login=?", (user.login, ))
            if cur.fetchone():
                return None
            cur.execute(
                "insert into users (login, email, password, active, admin) "
                "values (:login, :email, :password, :active, :admin)",
                _user_to_row(user))
            user.id = cur.lastrowid
        self._conn.commit()
        return user

    def update_schema(self):
        schema_ver = self._get_schema_version()
        _LOG.debug("current schema version: %r", schema_ver)
        schama_files = os.path.join(os.path.dirname(__file__), 'schema')
        for fname in sorted(os.listdir(schama_files)):
            if not fname.endswith('.sql'):
                continue
            try:
                version = int(os.path.splitext(fname)[0])
                _LOG.debug("found update: %r", version)
                if version <= schema_ver:
                    continue
            except ValueError:
                _LOG.warning("skipping schema update file %s", fname)
                continue
            _LOG.info("apply update: %s", fname)
            fpath = os.path.join(schama_files, fname)
            try:
                with open(fpath, 'r') as update_file:
                    self._conn.executescript(update_file.read())
                self._conn.execute(
                    'insert into schema_version(version) values(?)',
                    (version, ))
                self._conn.commit()
            except Exception as err:
                self._conn.rollback()
                _LOG.error("schema update error: %s", err)

    def _get_schema_version(self):
        try:
            cur = self._conn.cursor()
            cur.execute('select max(version) from schema_version')
            row = cur.fetchone()
            if row:
                return row[0] or 0
        except sqlite3.OperationalError:
            _LOG.info("no schema version")
        return 0


def _get_json_if_exists(row_keys, key, row, default=None):
    if key not in row_keys:
        return default
    value = row[key]
    return json.loads(value) if value else default


def _source_from_row(row):
    source = model.Source()
    source.id = row["source_id"]
    source.group_id = row["source_group_id"]
    source.kind = row["source_kind"]
    source.name = row["source_name"]
    source.interval = row["source_interval"]
    row_keys = row.keys()
    source.settings = _get_json_if_exists(row_keys, "source_settings", row)
    source.filters = _get_json_if_exists(row_keys, "source_filters", row)
    source.user_id = row['source_user_id']
    return source


def _source_to_row(source):
    return {
        'group_id': source.group_id,
        'kind': source.kind,
        'name': source.name,
        'interval': source.interval,
        'settings': json.dumps(source.settings) if source.settings else None,
        'filters': json.dumps(source.filters) if source.filters else None,
        'user_id': source.user_id,
        'id': source.id,
    }


def _state_from_row(row):
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
    state.state = _get_json_if_exists(row_keys, "source_state_state", row)
    return state


def _state_to_row(state):
    return (
        state.source_id,
        state.next_update,
        state.last_update,
        state.last_error,
        state.error_counter,
        state.success_counter,
        state.status,
        state.error,
        json.dumps(state.state)
    )


def _entry_from_row(row):
    entry = model.Entry(row["entry_id"])
    entry.source_id = row["entry_source_id"]
    entry.updated = row["entry_updated"]
    entry.created = row["entry_created"]
    entry.read_mark = row["entry_read_mark"]
    entry.star_mark = row["entry_star_mark"]
    entry.status = row["entry_status"]
    entry.oid = row["entry_oid"]
    entry.title = row["entry_title"]
    entry.url = row["entry_url"]
    row_keys = row.keys()
    entry.opts = _get_json_if_exists(row_keys, "entry_opts", row)
    if "entry_content" in row_keys:
        entry.content = row["entry_content"]
    entry.user_id = row['entry_user_id']
    return entry


def _entry_to_row(entry: model.Entry) -> ty.Dict[str, ty.Any]:
    return {
        'source_id': entry.source_id,
        'updated': entry.updated,
        'created': entry.created,
        'read_mark': entry.read_mark,
        'star_mark': entry.star_mark,
        'status': entry.status,
        'oid': entry.oid,
        'title': entry.title,
        'url': entry.url,
        'opts': json.dumps(entry.opts),
        'content': entry.content,
        'id': entry.id,
        'user_id': entry.user_id,
    }


def _user_from_row(row) -> model.User:
    return model.User(
        id_=row['id'],
        login=row['login'],
        email=row['email'],
        password=row['password'],
        active=row['active'],
        admin=row['admin']
    )


def _user_to_row(user: model.User):
    return {
        'id': user.id,
        'login': user.login,
        'email': user.email,
        'password': user.password,
        'active': user.active,
        'admin': user.admin
    }


def _setting_from_row(row) -> model.Setting:
    value = row['value']
    if value and isinstance(value, str):
        value = json.loads(value)
    return model.Setting(row['key'], value, row['value_type'],
                         row['description'])


def _source_group_from_row(row):
    return model.SourceGroup(row["source_group_id"],
                             row["source_group_name"],
                             row["source_group_user_id"])


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

_GET_ENTRY_BY_ID_SQL = '''
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
from entries where id=?

'''

_GET_ENTRY_BY_OID_SQL = '''
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
where oid=?
'''

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
    sg.user_id as source_group_user_id
from entries e
join sources s on s.id = e.source_id
left join source_groups sg on sg.id = s.group_id
'''

_GET_ENTRIES_SQL = _GET_ENTRIES_SQL_MAIN + '''
where e.user_id=:user_id
order by e.id
'''

_GET_UNREAD_ENTRIES_SQL = _GET_ENTRIES_SQL_MAIN + '''
where read_mark = 0 and e.user_id=:user_id
order by e.id
'''

_GET_UNREAD_ENTRIES_BY_SOURCE_SQL = _GET_ENTRIES_SQL_MAIN + '''
where read_mark = 0 and e.source_id=:source_id
order by e.id
'''

_GET_ENTRIES_BY_SOURCE_SQL = _GET_ENTRIES_SQL_MAIN + '''
where e.source_id=:source_id
order by e.id
'''

_GET_UNREAD_ENTRIES_BY_GROUP_SQL = _GET_ENTRIES_SQL_MAIN + '''
where read_mark = 0 and s.group_id=:group_id
order by e.id
'''

_GET_ENTRIES_BY_GROUP_SQL = _GET_ENTRIES_SQL_MAIN + '''
where s.group_id=:group_id
order by e.id
'''

_GET_STARRED_ENTRIES_SQL = _GET_ENTRIES_SQL_MAIN + '''
where e.star_mark = 1 and e.user_id=:user_id
order by e.id
'''

# _INSERT_ENTRY_SQL = """
# insert into entries (source_id, updated, created,
# read_mark, star_mark, status, oid, title, url, content)
# values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
# ON CONFLICT(oid) DO nothing;
# """

_INSERT_ENTRY_SQL = """
insert into entries (source_id, updated, created,
    read_mark, star_mark, status, oid, title, url, opts, content, user_id)
values (:source_id, :updated, :created,
    :read_mark, :star_mark, :status, :oid, :title, :url, :opts, :content,
    :user_id)
"""

_CHECK_ENTRY_SQL = """
select 1 from entries where oid=? and user_id=?
"""

_UPDATE_ENTRY_SQL = """
update entries set source_id=:source_id, updated=:updated, created=:created,
    read_mark=:read_mark, star_mark=:star_mark, status=:status, oid=:oid,
    title=:title, url=:url, opts=:opts, content=:content
where id=:id
"""

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


def _get_entries_get_sql(source_id, group_id, unread) -> str:
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
