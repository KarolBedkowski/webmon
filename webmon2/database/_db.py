# Copyright © 2021 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Definition of DB object
"""
from __future__ import annotations

import logging
import os.path
import sys
import typing as ty
from pathlib import Path

import psycopg2
from psycopg2 import extensions, extras, pool

_ = ty
_LOG = logging.getLogger("db")

psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
psycopg2.extras.register_default_json(globally=True)


class DB:
    INSTANCE = None
    POOL = None

    __slots__ = ("_conn",)

    def __init__(self) -> None:
        super().__init__()
        self._conn: ty.Optional[psycopg2.extensions.connection] = None
        if not DB.POOL:
            raise RuntimeError("DB.POOL not initialized")

    def connect(self) -> None:
        assert DB.POOL
        self._conn = DB.POOL.getconn()
        self._conn.autocommit = False
        self._conn.initialize(_LOG)

    @classmethod
    def get(cls) -> DB:
        return DB()

    def cursor(self) -> psycopg2.extensions.cursor:
        if not self._conn or self._conn.closed:
            self.close()
            self.connect()

        assert self._conn
        return self._conn.cursor(cursor_factory=extras.DictCursor)

    def begin(self) -> None:
        pass

    def commit(self) -> None:
        assert self._conn
        self._conn.commit()

    def rollback(self) -> None:
        assert self._conn
        self._conn.rollback()

    @classmethod
    def initialize(
        cls, conn_str: str, update_schema: bool, min_conn: int, max_conn: int
    ) -> None:
        _LOG.info("initializing database")
        cls.POOL = pool.ThreadedConnectionPool(
            min_conn,
            max_conn,
            conn_str,
            connection_factory=extras.LoggingConnection,
        )
        # common.create_missing_dir(os.path.dirname(filename))
        with DB() as db:
            db.check()
            if update_schema:
                db.update_schema()

    def __enter__(self) -> DB:
        # _LOG.debug("Enter conn %s", self._conn)
        return self

    def __exit__(
        self, type_: ty.Any, value: ty.Any, traceback: ty.Any
    ) -> bool:
        self.close()
        return isinstance(value, TypeError)

    def close(self) -> None:
        assert self.POOL
        if self._conn is not None:
            if self._conn.closed:
                self._conn = None
                return

            _LOG.debug("Closing conn %s", self._conn)
            if self._conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
                # prevent 'idle in transactions' connections
                self._conn.rollback()

            self.POOL.putconn(self._conn)
            self._conn = None

    def check(self) -> None:
        with self.cursor() as cur:
            cur.execute("select now()")
            _LOG.debug("check: %s", cur.fetchone())
            self.rollback()

    def update_schema(self) -> None:
        assert self._conn
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
                    sql = Path(fpath).read_text(encoding="UTF-8")
                    _LOG.debug("execute: %s", sql)
                    cur.execute(sql)
                    cur.execute(
                        "insert into schema_version(version) values(%s)",
                        (version,),
                    )
                self._conn.commit()

            except Exception as err:  # pylint: disable=broad-except
                self._conn.rollback()
                _LOG.exception("schema update error: %s", err)
                sys.exit(-1)

    def _get_schema_version(self) -> int:
        with self.cursor() as cur:
            try:
                cur.execute("select max(version) from schema_version")
                if row := cur.fetchone():
                    return row[0] or 0

            except psycopg2.ProgrammingError:
                _LOG.info("no schema version")

        return 0
