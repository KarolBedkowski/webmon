#!/usr/bin/python3
"""
Cache storage functions.

Copyright (c) Karol Będkowski, 2016-2021

This file is part of webmon.
Licence: GPLv2+
"""
import logging
import os.path
import sys
import typing as ty

import psycopg2
from psycopg2 import extensions, extras, pool

from . import binaries, entries, groups, scoring, settings, sources, users
from ._dbcommon import NotFound

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2021"
__all__ = (
    "NotFound",
    "DB",
    "settings",
    "users",
    "groups",
    "entries",
    "sources",
    "binaries",
    "scoring",
)

_ = ty
_LOG = logging.getLogger("db")

psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
psycopg2.extras.register_default_json(globally=True)


class DB:

    INSTANCE = None
    POOL = None

    def __init__(self) -> None:
        super().__init__()
        assert DB.POOL
        self._conn = DB.POOL.getconn()
        self._conn.initialize(_LOG)
        # _LOG.debug("conn: %s", self._conn)

    @classmethod
    def get(cls):
        return DB()

    def cursor(self):
        return self._conn.cursor(cursor_factory=extras.DictCursor)

    def begin(self):
        pass

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    @classmethod
    def initialize(cls, conn_str: str, update_schema: bool):
        _LOG.info("initializing database")
        conn_str = extensions.parse_dsn(conn_str)
        cls.POOL = pool.ThreadedConnectionPool(
            1, 20, connection_factory=extras.LoggingConnection, **conn_str
        )
        # common.create_missing_dir(os.path.dirname(filename))
        with DB() as db:
            db.check()
            if update_schema:
                db.update_schema()

    def __enter__(self):
        # _LOG.debug("Enter conn %s", self._conn)
        return self

    def __exit__(self, type_, value, traceback):
        self.close()
        return isinstance(value, TypeError)

    def close(self):
        if self._conn is not None:
            # _LOG.debug("Closing conn %s", self._conn)
            self.POOL.putconn(self._conn)
            self._conn = None

    def check(self):
        with self.cursor() as cur:
            cur.execute("select now()")
            _LOG.debug("check: %s", cur.fetchone())
            self.rollback()

    def update_schema(self):
        self._conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        schema_ver = self._get_schema_version()
        _LOG.debug("current schema version: %r", schema_ver)
        schema_files = os.path.join(os.path.dirname(__file__), "..", "schema")
        for fname in sorted(os.listdir(schema_files)):
            if not fname.endswith(".sql"):
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
            fpath = os.path.join(schema_files, fname)
            try:
                with self._conn.cursor() as cur:
                    with open(fpath) as update_file:
                        cur.execute(update_file.read())
                    cur.execute(
                        "insert into schema_version(version) values(%s)",
                        (version,),
                    )
                self._conn.commit()
            except Exception as err:  # pylint: disable=broad-except
                self._conn.rollback()
                _LOG.exception("schema update error: %s", err)
                sys.exit(-1)

    def _get_schema_version(self):
        with self.cursor() as cur:
            try:
                cur.execute("select max(version) from schema_version")
                row = cur.fetchone()
                if row:
                    return row[0] or 0
            except psycopg2.ProgrammingError:
                _LOG.info("no schema version")
            return 0
