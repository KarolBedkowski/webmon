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
    user_pass_adm = args.split(":")
    if len(user_pass_adm) < 2:
        print("wrong arguments for --add-user")
        return
    user = model.User(login=user_pass_adm[0], active=True)
    user.password = security.hash_password(user_pass_adm[1])
    user.admin = len(user_pass_adm) > 2 and user_pass_adm[2] == "admin"
    with database.DB.get() as db:
        user = database.users.save(db, user)
        db.commit()
    if not user:
        print("user already exists")
    else:
        print("user created")


def change_user_pass(args):
    user_pass = args.split(":")
    if len(user_pass) != 2:
        print("wrong arguments for --reset-password; required login:pass")
        return
    with database.DB.get() as db:
        user = database.users.get(db, login=user_pass[0])
        if not user:
            print("user not found")
            return
        user.password = security.hash_password(user_pass[1])
        user = database.users.save(db, user)
        db.commit()
        print("password changed")


def remove_user_totp(login):
    if not login:
        print("missing login arguments for --remove-user-totp")
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
    if args.add_user:
        add_user(args.add_user)
        return True

    if args.change_user_pass:
        change_user_pass(args.change_user_pass)
        return True

    if args.remove_user_totp:
        change_user_pass(args.remove_user_totp)
        return True

    if args.migrate_filename:
        from . import migrate

        migrate.migrate(args.migrate_filename)
        return True

    return False
