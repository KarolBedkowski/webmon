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

import argparse
import configparser
import os
import sys
import typing as ty

from webmon2 import model

from . import common, conf, database, filters, security, sources


def _show_abilities_cls(title: str, base_cls: ty.Any) -> None:
    print(title)
    for name, cls in common.get_subclasses_with_name(base_cls):
        print("  -", name)
        if hasattr(cls, "description"):
            print("    " + cls.description)

        if hasattr(cls, "params") and cls.params:
            print("    Parameters:")
            for param in cls.params:
                print(
                    f"     - {param.name:<17}\t{param.description:<32s}"
                    "\tdefault={param.default!r:<10}\t"
                    + ("Required" if param.required else "")
                )
    print()


def show_abilities() -> None:
    _show_abilities_cls("Sources:", sources.AbstractSource)
    _show_abilities_cls("Filters:", filters.AbstractFilter)


def add_user(args: argparse.Namespace) -> None:
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


def change_user_pass(args: argparse.Namespace) -> None:
    login = args.login
    password = args.password
    if not login or not password:
        print("wrong arguments for change password")
        return

    with database.DB.get() as db:
        try:
            user = database.users.get(db, login=login)
        except database.NotFound:
            print("user not found")
            return

        user.password = security.hash_password(password)
        user = database.users.save(db, user)
        db.commit()
        print("password changed")


def remove_user_totp(args: argparse.Namespace) -> None:
    login = args.login
    if not login:
        print("missing login arguments for remove totp")
        return
    with database.DB.get() as db:
        try:
            user = database.users.get(db, login=login)
        except database.NotFound:
            print("user not found")
            return

        user.totp = None
        user = database.users.save(db, user)
        db.commit()
        print("user changed")


def write_config_file(
    args: argparse.Namespace, app_conf: configparser.ConfigParser
) -> None:
    filename = args.conf_filename
    if not filename:
        print("missing destination filename", file=sys.stderr)
        return

    filename = os.path.expanduser(filename)

    if os.path.isfile(filename):
        print(f"missing file '{filename}' already exists", file=sys.stderr)
        return

    try:
        conf.save_conf(app_conf, filename)
    except Exception as err:  # pylint: disable=broad-except
        print(
            f"write config file to '{filename}' error: {err}", file=sys.stderr
        )
    else:
        print("Done")


# pylint: disable=import-outside-toplevel
def shell(
    args: argparse.Namespace, app_conf: configparser.ConfigParser
) -> None:
    try:
        import IPython
        from IPython.terminal.ipapp import load_default_config
    except ImportError:
        print("IPython not available", file=sys.stderr)
        return

    from webmon2.web import app as web_app

    app = web_app.create_app(args, app_conf)
    config = load_default_config()
    IPython.start_ipython(
        user_ns=app.make_shell_context(),
        config=config,
        argv=[],
    )


def process_cli(
    args: argparse.Namespace, app_conf: configparser.ConfigParser
) -> bool:
    if args.cmd == "users":
        if args.subcmd == "add":
            add_user(args)
        elif args.subcmd == "passwd":
            change_user_pass(args)
        elif args.subcmd == "remove_totp":
            remove_user_totp(args)

        print("unknown sub command", file=sys.stderr)
        return True

    if args.cmd == "migrate":
        # pylint: disable=import-outside-toplevel
        from . import migrate

        migrate.migrate(args)
        return True

    if args.cmd == "write-config":
        write_config_file(args, app_conf)
        return True

    if args.cmd == "shell":
        shell(args, app_conf)
        return True

    return False
