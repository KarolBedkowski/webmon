#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2021
#
# Distributed under terms of the GPLv3 license.

"""
Access & manage users in db
"""
import logging
import typing as ty

from webmon2 import model

from . import _dbcommon as dbc
from ._db import DB
from ._dbcommon import tyCursor

_LOG = logging.getLogger(__name__)


class LoginAlreadyExistsError(Exception):
    pass


_GET_ALL_SQL = """
select id as user__id, login as user__login, email as user__email,
    password as user__password, active as user__admin, admin as user__admin,
    active as user__active,
    totp as user__totp
from users
"""


def get_all(db: DB) -> ty.Iterable[model.User]:
    """Get all users"""
    with db.cursor() as cur:
        cur.execute(_GET_ALL_SQL)
        for row in cur:
            yield model.User.from_row(row)


_GET_BY_ID_SQL = """
select id as user__id, login as user__login, email as user__email,
    password as user__password, active as user__admin, admin as user__admin,
    active as user__active,
    totp as user__totp
from users
where id=%s
"""

_GET_BY_LOGIN_SQL = """
select id as user__id, login as user__login, email as user__email,
    password as user__password, active as user__admin, admin as user__admin,
    active as user__active,
    totp as user__totp
from users
where login=%s
"""


def get(
    db: DB, id_: ty.Optional[int] = None, login: ty.Optional[str] = None
) -> model.User:
    """Get user by id or login"""
    with db.cursor() as cur:
        if id_:
            cur.execute(_GET_BY_ID_SQL, (id_,))
        elif login:
            cur.execute(_GET_BY_LOGIN_SQL, (login,))
        else:
            raise AttributeError("missing id or login")

        row = cur.fetchone()

    if not row:
        raise dbc.NotFound()

    return model.User.from_row(row)


_UPDATE_USER_SQL = """
update users set login=%(user__login)s, email=%(user__email)s,
password=%(user__password)s, active=%(user__active)s, admin=%(user__admin)s,
totp=%(user__totp)s
where id=%(user__id)s
"""
_INSERT_USER_SQL = """
insert into users (login, email, password, active, admin, totp)
values (%(user__login)s, %(user__email)s, %(user__password)s, %(user__active)s,
    %(user__admin)s, %(user__totp)s)
returning id
"""


def save(db: DB, user: model.User) -> model.User:
    """Insert or update user"""
    with db.cursor() as cur:
        if user.id:
            cur.execute(_UPDATE_USER_SQL, user.to_row())
        else:
            cur.execute("select 1 from users where login=%s", (user.login,))
            if cur.fetchone():
                cur.close()
                raise LoginAlreadyExistsError()

            cur.execute(_INSERT_USER_SQL, user.to_row())
            user_id = cur.fetchone()[0]
            user.id = user_id
            _create_new_user_data(cur, user_id)

    return user


def _create_new_user_data(cur: tyCursor, user_id: int) -> None:
    cur.execute(
        "select count(1) from source_groups where user_id=%s", (user_id,)
    )
    if not cur.fetchone()[0]:
        cur.execute(
            "insert into source_groups(user_id, name) values (%s, %s)",
            (user_id, "main"),
        )


State = ty.Any


def get_state(
    db: DB,
    user_id: int,
    key: str,
    default: ty.Optional[State] = None,
    conv: ty.Optional[ty.Callable[[str], State]] = None,
) -> State:
    with db.cursor() as cur:
        cur.execute(
            "select value from users_state where user_id=%s and key=%s",
            (user_id, key),
        )
        row = cur.fetchone()
        if not row:
            return default

        value = row[0]
        return conv(value) if conv else value


_SET_STATE_SQL = """
INSERT INTO users_state (user_id, key, value)
VALUES (%s, %s, %s)
ON CONFLICT ON CONSTRAINT users_state_pkey
DO UPDATE SET value=EXCLUDED.value
"""


def set_state(db: DB, user_id: int, key: str, value: ty.Any) -> None:
    with db.cursor() as cur:
        cur.execute(_SET_STATE_SQL, (user_id, key, value))


_DELETE_USER_SQL = """
    DELETE FROM users WHERE id=%s
"""


def delete(db: DB, user_id: int) -> None:
    with db.cursor() as cur:
        cur.execute(_DELETE_USER_SQL, (user_id,))
