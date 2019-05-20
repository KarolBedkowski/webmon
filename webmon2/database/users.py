#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2019
#
# Distributed under terms of the GPLv3 license.

"""
Access & manage users in db
"""
import typing as ty
import logging

from webmon2 import model


_LOG = logging.getLogger(__name__)


class LoginAlreadyExistsError(Exception):
    pass


def get_all(db) -> ty.Iterable[model.User]:
    """ Get all users """
    with db.cursor() as cur:
        cur.execute(
            "select id, login, email, password, active, admin from users")
        for row in cur:
            yield _user_from_row(row)


def get(db, id_=None, login=None) -> ty.Optional[model.User]:
    """ Get user by id or login """
    with db.cursor() as cur:
        if id_:
            cur.execute("select id, login, email, password, active, admin "
                        "from users where id=%s", (id_, ))
        elif login:
            cur.execute("select id, login, email, password, active, admin "
                        "from users where login=%s", (login, ))
        else:
            return None
        row = cur.fetchone()
        if not row:
            return None
        user = _user_from_row(row)
        return user


def save(db, user: model.User) -> model.User:
    """ Insert or update user """
    cur = db.cursor()
    if user.id:
        cur.execute(
            "update users set login=%(login)s, email=%(email)s, "
            "password=%(password)s, active=%(active)s, admin=%(admin)s "
            "where id=%(id)s",
            _user_to_row(user))
    else:
        cur.execute("select 1 from users where login=%s", (user.login, ))
        if cur.fetchone():
            cur.close()
            raise LoginAlreadyExistsError()
        cur.execute(
            "insert into users (login, email, password, active, admin) "
            "values (%(login)s, %(email)s, %(password)s, %(active)s, "
            "%(admin)s) returning id",
            _user_to_row(user))
        user.id = cur.fetchone()[0]
        _create_new_user_data(cur, user.id)

    cur.close()
    return user


def _create_new_user_data(cur, user_id: int):
    cur.execute(
        "select count(1) from source_groups where user_id=%s",
        (user_id, ))
    if not cur.fetchone()[0]:
        cur.execute(
            "insert into source_groups(user_id, name) values (%s, %s)",
            (user_id, "main"))


def _user_from_row(row) -> model.User:
    return model.User(
        id=row['id'],
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


def get_state(db, user_id: int, key: str, default=None, conv=None):
    with db.cursor() as cur:
        cur.execute(
            "select value from users_state where user_id=%s and key=%s",
            (user_id, key))
        row = cur.fetchone()
        if not row:
            return default
        value = row[0]
        _LOG.debug("value: %r, %r", value, conv)
        return conv(value) if conv else value


def set_state(db, user_id: int, key: str, value):
    with db.cursor() as cur:
        cur.execute(
            "insert into users_state (user_id, key, value) "
            "values (%s, %s, %s) "
            "ON CONFLICT ON CONSTRAINT users_state_pkey "
            "DO UPDATE SET value=EXCLUDED.value",
            (user_id, key, value))
