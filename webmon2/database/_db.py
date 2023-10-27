# Copyright © 2021-2023 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Definition of DB object
"""
from __future__ import annotations

import os.path
import sys
import typing as ty
from functools import cache
from pathlib import Path

import psycopg
import psycopg_pool as pool
import structlog

T = ty.TypeVar("T")

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)


@cache
def create_object_row_maker(
    from_row: ty.Callable[[dict[str, ty.Any]], T]
) -> psycopg.rows.RowFactory[T]:
    """create RowMaker for `from_row` callable that create `T` objects."""

    def row_factory(
        cursor: psycopg.Cursor[ty.Any],
    ) -> psycopg.rows.RowMaker[T]:
        fields = [c.name for c in cursor.description or ()]

        def make_row(values: ty.Sequence[ty.Any]) -> T:
            data = dict(zip(fields, values))
            return from_row(data)

        return make_row

    return row_factory


class DB:
    POOL: pool.ConnectionPool = None  # type: ignore

    __slots__ = ("_conn", "_log")

    def __init__(self) -> None:
        super().__init__()
        self._conn: psycopg.Connection[ty.Any] | None = None
        if not DB.POOL:
            raise RuntimeError("DB.POOL not initialized")

    def connect(self) -> None:
        assert DB.POOL
        _LOG.debug("db: connect")
        self._conn = DB.POOL.getconn()
        if not self._conn:
            raise RuntimeError("no database connection")

    @classmethod
    def get(cls) -> DB:
        return DB()

    def cursor_dict_row(self) -> psycopg.Cursor[dict[str, ty.Any]]:
        if not self._conn or self._conn.closed:
            self.close()
            self.connect()

        assert self._conn
        return self._conn.cursor(row_factory=psycopg.rows.dict_row)

    def cursor(self) -> psycopg.Cursor[tuple[ty.Any, ...]]:
        if not self._conn or self._conn.closed:
            self.close()
            self.connect()

        assert self._conn
        return self._conn.cursor()

    def cursor_obj_row(
        self, from_row: ty.Callable[[dict[str, ty.Any]], T]
    ) -> psycopg.Cursor[T]:
        if not self._conn or self._conn.closed:
            self.close()
            self.connect()

        assert self._conn
        return self._conn.cursor(row_factory=create_object_row_maker(from_row))

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
        cls.POOL = pool.ConnectionPool(
            conn_str,
            min_size=min_conn,
            max_size=max_conn,
            kwargs={"autocommit": False},
        )

        with DB() as db:
            db.check()
            if update_schema:
                db.update_schema()

    def __enter__(self) -> DB:
        return self

    def __exit__(
        self, type_: ty.Any, value: ty.Any, traceback: ty.Any
    ) -> bool:
        self.close()
        return isinstance(value, TypeError)

    def close(self) -> None:
        assert self.POOL
        if self._conn is None:
            return

        if self._conn.closed:
            self.POOL.putconn(self._conn)
            self._conn = None
            return

        _LOG.debug("db: closing connection")
        if (
            self._conn.info.transaction_status
            == psycopg.pq.TransactionStatus.INTRANS
        ):
            # prevent 'idle in transactions' connections
            self._conn.rollback()

        self.POOL.putconn(self._conn)
        self._conn = None

    def check(self) -> None:
        with self.cursor() as cur:
            cur.execute("select now()")
            _dummy = cur.fetchone()
            self.rollback()

    def update_schema(self) -> None:
        assert self._conn
        self._conn.autocommit = True
        log = _LOG.bind()

        schema_ver = self._get_schema_version()
        log.debug("db.update_schema: current version: %r", schema_ver)

        schema_files = Path(__file__).parent.joinpath("..", "schema")
        log.debug("db.update_schema: schema_dir: %s", schema_files)
        for fname in sorted(os.listdir(schema_files)):
            if not fname.endswith(".sql"):
                continue

            try:
                version = int(os.path.splitext(fname)[0])
                log.debug("db.update_schema: found update %r", version)
                if version <= schema_ver:
                    continue

            except ValueError as err:
                log.warning(
                    "db.update_schema: skipping file %r", fname, error=err
                )
                continue

            log.info("db.update_schema: apply update from file %r", fname)
            fpath = Path(schema_files, fname)
            try:
                with self._conn.cursor() as cur:
                    sql = fpath.read_text(encoding="UTF-8")
                    log.debug("db.update_schema: execute query", sql=sql)
                    cur.execute(sql)
                    cur.execute(
                        "insert into schema_version(version) values(%s)",
                        (version,),
                    )
                self._conn.commit()

            except Exception as err:  # pylint: disable=broad-except
                self._conn.rollback()
                log.exception(
                    "db.update_schema: execute file %r error", fpath, error=err
                )
                sys.exit(-1)

    def _get_schema_version(self) -> int:
        with self.cursor() as cur:
            try:
                cur.execute("select max(version) from schema_version")
                if row := cur.fetchone():
                    return row[0] or 0

            except psycopg.ProgrammingError:
                _LOG.info("db: no schema version found")

        return 0
