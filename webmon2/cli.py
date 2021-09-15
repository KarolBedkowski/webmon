#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
command line commands
"""

import sys

from . import database, sources, filters, common, security
from webmon2 import model


def _show_abilities_cls(title, base_cls):
    print(title)
    for name, cls in common.get_subclasses_with_name(base_cls):
        print("  -", name)
        if hasattr(cls, "description"):
            print("    " + cls.description)

        if hasattr(cls, "params") and cls.params:
            print("    Parameters:")
            for param in cls.params:
                print(
                    "     - {:<15s}\t{:<20s}\tdefault={!r:<10}\t{}".format(
                        param.name,
                        param.description,
                        param.default,
                        "Required" if param.required else "",
                    )
                )
    print()


def show_abilities():
    _show_abilities_cls("Sources:", sources.AbstractSource)
    _show_abilities_cls("Filters:", filters.AbstractFilter)


def add_user(args):
    login = args.login
    password = args.password
    admin = args.admin
    if not login or not password:
        print("wrong arguments for add user")
        return
    user = model.User(login=login, active=True)
    user.password = security.hash_password(password)
    user.admin = bool(admin)
    with database.DB.get() as db:
        user = database.users.save(db, user)
        db.commit()
    if not user:
        print("user already exists")
    else:
        print("user created")


def change_user_pass(args):
    login = args.login
    password = args.password
    if not login or not password:
        print("wrong arguments for change password")
        return
    with database.DB.get() as db:
        user = database.users.get(db, login=login)
        if not user:
            print("user not found")
            return
        user.password = security.hash_password(password)
        user = database.users.save(db, user)
        db.commit()
        print("password changed")


def remove_user_totp(args):
    login = args.login
    if not login:
        print("missing login arguments for remove totp")
        return
    with database.DB.get() as db:
        user = database.users.get(db, login=login)
        if not user:
            print("user not found")
            return
        user.totp = None
        user = database.users.save(db, user)
        db.commit()
        print("user changed")


def process_cli(args) -> bool:
    if args.cmd == "users":
        if args.subcmd == "add":
            add_user(args)
            return True
        if args.subcmd == "passwd":
            change_user_pass(args)
            return True
        if args.subcmd == "remove_totp":
            remove_user_totp(args)
            return True
        print("unknown sub command", file=sys.stderr)
    elif args.cmd == "migrate":
        from . import migrate

        migrate.migrate(args)
        return True

    return False
