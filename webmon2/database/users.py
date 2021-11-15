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

_LOG = logging.getLogger(__name__)


class LoginAlreadyExistsError(Exception):
    pass


_GET_ALL_SQL = """
SELECT id AS user__id, login AS user__login, email AS user__email,
    password AS user__password, active AS user__admin, admin AS user__admin,
    active AS user__active, totp AS user__totp
FROM users
"""


def get_all(db: DB) -> ty.Iterable[model.User]:
    """Get all users"""
    with db.cursor() as cur:
        cur.execute(_GET_ALL_SQL)
        for row in cur:
            yield model.User.from_row(row)


_GET_ACTIVE_SQL = """
SELECT id AS user__id, login AS user__login, email AS user__email,
    password AS user__password, active AS user__admin, admin AS user__admin,
    active AS user__active, totp AS user__totp
FROM users
WHERE active
"""


def get_all_active(db: DB) -> ty.Iterable[model.User]:
    """Get all active users"""
    with db.cursor() as cur:
        cur.execute(_GET_ACTIVE_SQL)
        for row in cur:
            yield model.User.from_row(row)


_GET_BY_ID_SQL = """
SELECT id AS user__id, login AS user__login, email AS user__email,
    password AS user__password, active AS user__admin, admin AS user__admin,
    active AS user__active, totp AS user__totp
FROM users
WHERE id=%s
"""

_GET_BY_LOGIN_SQL = """
SELECT id AS user__id, login AS user__login, email AS user__email,
    password AS user__password, active AS user__admin, admin AS user__admin,
    active AS user__active, totp AS user__totp
FROM users
WHERE login=%s
"""


def get(
    db: DB, id_: ty.Optional[int] = None, login: ty.Optional[str] = None
) -> model.User:
    """Get user by id or login.

    Args:
        db: database object
        id_: user id; required if `login` is not given
        login: user login; require if `id_` is not given

    Raises:
        `NotFound`: user not found

    Return:
        `User`

    """
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
UPDATE users SET login=%(user__login)s, email=%(user__email)s,
    password=%(user__password)s, active=%(user__active)s, admin=%(user__admin)s,
    totp=%(user__totp)s
WHERE id=%(user__id)s
"""
_INSERT_USER_SQL = """
INSERT INTO users (login, email, password, active, admin, totp)
VALUES (%(user__login)s, %(user__email)s, %(user__password)s, %(user__active)s,
    %(user__admin)s, %(user__totp)s)
RETURNING id
"""


def save(db: DB, user: model.User) -> model.User:
    """Insert or update user.

    Raises:
        `LoginAlreadyExistsError`: login exist for another user  (check only for
            new user)

    Return:
        updated user
    """
    if user.id:
        with db.cursor() as cur:
            cur.execute(_UPDATE_USER_SQL, user.to_row())
    else:
        # check is login exists
        with db.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE login=%s", (user.login,))
            if cur.fetchone():
                raise LoginAlreadyExistsError()

        with db.cursor() as cur:
            cur.execute(_INSERT_USER_SQL, user.to_row())
            user_id = cur.fetchone()[0]
            user.id = user_id

        _create_new_user_data(db, user_id)

    return user


def _create_new_user_data(db: DB, user_id: int) -> None:
    """Create default sources group when not exists for given user"""
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(1) FROM source_groups WHERE user_id=%s", (user_id,)
        )
        if cur.fetchone()[0]:
            return

    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO source_groups(user_id, name) VALUES (%s, %s)",
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
    """Get state value for given user.

    Args:
        db: database object
        user_id: user id
        key: state key
        default: default value if given key not exists; default None
        conv: optional function used to convert string value to expected type

    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT value FROM users_state WHERE user_id=%s AND key=%s",
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
    """Update / store state value for `user_id` and `key`."""
    with db.cursor() as cur:
        cur.execute(_SET_STATE_SQL, (user_id, key, value))


def delete(db: DB, user_id: int) -> None:
    """Remove user from database."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
