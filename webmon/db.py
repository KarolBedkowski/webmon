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

from . import common, model

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"

_LOG = logging.getLogger("db")


class NotFound(Exception):
    pass


class DB(object):

    def __init__(self, filename: str) -> None:
        super().__init__()
        self._filename = filename
        self._conn = sqlite3.connect(self._filename, timeout=10,
                                     isolation_level="EXCLUSIVE",
                                     detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript("PRAGMA journal_mode=WAL")

    def clone(self):
        return DB(self._filename)

    @staticmethod
    def initialize(filename):
        common.create_missing_dir(os.path.dirname(filename))
        db = DB(filename)
        db._update_schema()
        return db

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def get_groups(self):
        cur = self._conn.cursor()
        cur.execute("select id, name from source_groups")
        groups = [model.SourceGroup(id, name)
                  for id, name in cur]
        return groups

    def get_group(self, id_):
        cur = self._conn.cursor()
        cur.execute("select id, name from source_groups where id=?", (id_, ))
        row = cur.fetchone()
        if not row:
            raise NotFound
        return model.SourceGroup(row[0], row[1])

    def save_group(self, group):
        cur = self._conn.cursor()
        if group.id is None:
            cur.execute("insert into source_groups (name) values (?)",
                        (group.name, ))
            group.id = cur.lastrowid
        else:
            cur.execute("update source_groups set name=? where id=?",
                        (group.name, group.id))
        self._conn.commit()
        return group

    def get_source(self, id_, with_state=False, with_group=True):
        cur = self._conn.cursor()
        cur.execute(_GET_SOURCE_SQL, (id_, ))
        row = cur.fetchone()
        if row is None:
            raise NotFound()

        source = _source_from_row(row)
        if with_state:
            source.state = self.get_state(source.id)
        if with_group:
            source.group = self.get_group(source.group_id)

        return source

    def save_source(self, source):
        cur = self._conn.cursor()
        row = _source_to_row(source)
        if source.id is None:
            cur.execute(_INSERT_SOURCE_SQL, row)
            source.id = cur.lastrowid
        else:
            row.append(source.id)
            cur.execute(_UPDATE_SOURCE_SQL, row)
        self._conn.commit()
        return source

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
               cur.execute("""select source_id
                           from source_state
                           where next_update <= datetime('now')""")
               ]
        return ids

    def get_unread_entries(self):
        cur = self._conn.cursor()
        for row in cur.execute(_GET_UNREAD_ENTRIES_SQL):
            entry = _entry_from_row(row)
            entry.source = _source_from_row(row)
            if entry.source.group_id:
                entry.source.group = _source_group_from_row(row)
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
            row.append(entry.id)
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
            cur.execute(_CHECK_ENTRY_SQL, (entry.oid, )).fetchone() is None
        ]
        _LOG.debug("new entries: %d", len(rows))
        cur.executemany(_INSERT_ENTRY_SQL, rows)
        self._conn.commit()

    def get_setting(self, key, converter=None):
        cur = self._conn.cursor()
        cur.execute("select value from settings where key=?", (key, ))
        row = cur.fetchone()
        if row is None:
            return None
        if converter is not None:
            return converter(row[0])
        return row[0]

    def _update_schema(self):
        schema_ver = self._get_schema_version()
        _LOG.info("current schema version: %r", schema_ver)
        schama_files = os.path.join(os.path.dirname(__file__), 'schema')
        for fname in os.listdir(schama_files):
            try:
                version = int(os.path.splitext(fname)[0])
                _LOG.info("found update: %r", version)
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
    return source


def _source_to_row(source):
    return [
        source.id,
        source.group_id,
        source.kind,
        source.name,
        source.interval,
        json.dumps(source.settings),
        json.dumps(source.filters)
    ]


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
    return entry


def _entry_to_row(entry):
    return [
        entry.source_id,
        entry.updated,
        entry.created,
        entry.read_mark,
        entry.star_mark,
        entry.status,
        entry.oid,
        entry.title,
        entry.url,
        json.dumps(entry.opts),
        entry.content,
    ]


def _source_group_from_row(row):
    return model.SourceGroup(row["source_group_id"],
                             row["source_group_name"])


_GET_SOURCE_SQL = """
select id as source_id, group_id as source_group_id,
    kind as source_kind, name as source_name, interval as source_interval,
    settings as source_settings, filters as source_filters
from sources where id=?
"""

_INSERT_SOURCE_SQL = """
insert into sources (group_id, kind, name, interval, settings, filters)
values (?, ?, ?, ?, ?, ?)
"""

_UPDATE_SOURCE_SQL = """
update sources set group_id=?, kind=?, name=?, interval=?, settings=?,
    filters=?
where id=?"""

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
    content as entry_content
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
    content as entry_content
where oid=?
'''

_GET_UNREAD_ENTRIES_SQL = '''
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
    s.id as source_id, s.group_id as source_group_id, s.kind as source_kind,
    s.name as source_name, s.interval as source_interval,
    sg.id as source_group_id, sg.name as source_group_name
from entries e
join sources s on s.id = e.source_id
left join source_groups sg on sg.id = s.group_id
where read_mark = 0
'''

# _INSERT_ENTRY_SQL = """
# insert into entries (source_id, updated, created,
# read_mark, star_mark, status, oid, title, url, content)
# values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
# ON CONFLICT(oid) DO nothing;
# """

_INSERT_ENTRY_SQL = """
insert into entries (source_id, updated, created,
read_mark, star_mark, status, oid, title, url, opts, content)
values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_CHECK_ENTRY_SQL = """
select 1 from entries where oid=?
"""

_UPDATE_ENTRY_SQL = """
update entries set source_id=?, updated=?, created=?, read_mark=?, star_mark=?,
status=?, oid=?, title=?, url=?, opts=?, content=?
where id=?
"""
