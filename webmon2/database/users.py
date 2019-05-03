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

from webmon2 import model


def get_all(db) -> ty.Iterable[model.User]:
    cur = db.cursor()
    for row in cur.execute(
            "select id, login, email, password, active, admin from users"):
        yield _user_from_row(row)


def get(db, id_=None, login=None) -> ty.Optional[model.User]:
    cur = db.cursor()
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


def save(db, user: model.User) -> ty.Optional[model.User]:
    cur = db.cursor()
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
    db.commit()
    return user


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
