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
import typing as ty

from webmon2 import common
from . import settings, users, groups, entries, sources
from ._dbcommon import NotFound

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"
__all__ = (
    "NotFound",
    "DB",
    "settings",
    "users",
    "groups",
    "entries",
    "sources"
)

_ = ty
_LOG = logging.getLogger("db")


class DB:

    INSTANCE = None

    def __init__(self, filename: str) -> None:
        super().__init__()
        self._filename = filename
        self._conn = sqlite3.connect(self._filename, timeout=30,
                                     isolation_level="EXCLUSIVE",
                                     detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA timeout=30000")
        self._conn.execute("PRAGMA busy_timeout = 30000")

    def clone(self):
        return DB(self._filename)

    @classmethod
    def get(cls):
        return cls.INSTANCE.clone()

    def cursor(self):
        return self._conn.cursor()

    def begin(self):
        # return self._conn.execute("begin deferred transaction")
        pass

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    @property
    def total_changes(self) -> int:
        return self._conn.total_changes

    @classmethod
    def initialize(cls, filename: str, update_schema: bool):
        _LOG.info("initializing database: %s", filename)
        common.create_missing_dir(os.path.dirname(filename))
        db = DB(filename)
        if update_schema:
            db.update_schema()
        db.close()
        cls.INSTANCE = db
        return db

    def __enter__(self):
        _LOG.debug("Enter conn %s", id(self._conn))
        return self

    def __exit__(self, type_, value, traceback):
        self.close()
        return isinstance(value, TypeError)

    def close(self):
        if self._conn is not None:
            _LOG.debug("Closing conn %s", id(self._conn))
#            self._conn.executescript("PRAGMA optimize")
            self._conn.close()
            self._conn = None

    def update_schema(self):
        schema_ver = self._get_schema_version()
        _LOG.debug("current schema version: %r", schema_ver)
        schama_files = os.path.join(os.path.dirname(__file__), '..', 'schema')
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
