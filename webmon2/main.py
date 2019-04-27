#!/usr/bin/python3
"""
Main functions.

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""

import argparse
import imp
import locale
import logging
import os.path
import typing as ty


from . import database, inputs, logging_setup, filters, common
from . import worker
from . import web

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"
_ = ty

VERSION = "2.0"
APP_NAME = "webmon2"

_LOG = logging.getLogger("main")
_DEFAULT_DB_FILE = "~/.local/share/" + APP_NAME + "/" + APP_NAME + ".db"


def _parse_options():
    parser = argparse.ArgumentParser(description=APP_NAME + " " + VERSION)
    parser.add_argument("-s", "--silent", action="store_true",
                        help="show only errors and warnings")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show additional informations")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="print debug informations")
    parser.add_argument('--log',
                        help='log file name')
    parser.add_argument("--abilities", action="store_true",
                        help="show available filters/inputs/outputs/"
                        "comparators")
    parser.add_argument('--database-file',
                        default=_DEFAULT_DB_FILE,
                        help='path to cache directory')
    parser.add_argument("--migrate",
                        help="migrate inputs from file",
                        dest="migrate_filename")
    parser.add_argument("--add-user",
                        help="add user; arguments in form "
                        "<login>:<password>[:admin]",
                        dest="add_user")
    parser.add_argument("--web-app-root", default="/")
    return parser.parse_args()


def _show_abilities_cls(title, base_cls):
    print(title)
    for name, cls in common.get_subclasses_with_name(base_cls):
        print("  -", name)
        if hasattr(cls, "description"):
            print("    " + cls.description)

        if hasattr(cls, "params") and cls.params:
            print("    Parameters:")
            for param in cls.params:
                print("     - {:<15s}\t{:<20s}\tdef={!r:<10}\treq={!r}".format(
                    *param))
    print()


def show_abilities():
    _show_abilities_cls("Inputs:", inputs.AbstractInput)
    _show_abilities_cls("Filters:", filters.AbstractFilter)


def add_user(args):
    from webmon2 import model
    user_pass_adm = args.split(':')
    if len(user_pass_adm) < 2:
        print("wrong arguments for --add-user")
        return
    user = model.User(login=user_pass_adm[0], active=True)
    user.hash_password(user_pass_adm[1])
    user.admin = len(user_pass_adm) > 2 and user_pass_adm[2] == 'admin'
    with database.DB.get() as db:
        user = db.save_user(user)
    if not user:
        print("user already exists")
    else:
        print("user created")


def _load_user_classes():
    users_scripts_dir = os.path.expanduser("~/.local/share/" + APP_NAME)
    if not os.path.isdir(users_scripts_dir):
        return

    for fname in os.listdir(users_scripts_dir):
        fpath = os.path.join(users_scripts_dir, fname)
        if os.path.isfile(fpath) and fname.endswith(".py") \
                and not fname.startswith("_"):
            _LOG.debug("loading %r", fpath)
            try:
                imp.load_source(fname[:-3], fpath)
            except ImportError as err:
                _LOG.error("Importing '%s' error %s", fpath, err)


def _check_libraries():
    try:
        from lxml import etree
    except ImportError:
        _LOG.warn("missing lxml library")
    try:
        import cssselect
    except ImportError:
        _LOG.warn("missing cssselect library")
    try:
        import html2text
    except ImportError:
        _LOG.warn("missing html2text library")
    try:
        import docutils.core
    except ImportError:
        _LOG.warn("missing docutils library")
    try:
        import yaml
    except ImportError:
        _LOG.warn("missing yaml library")
    try:
        import requests
    except ImportError:
        _LOG.warn("missing requests library")
    try:
        import feedparser
    except ImportError:
        _LOG.warn("missing feedparser library")
    try:
        import github3
    except ImportError:
        _LOG.warn("missing github3 library")


def main():
    """Main function."""

    try:
        locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())
    except locale.Error:
        pass

    args = _parse_options()
    logging_setup.setup(args.log, args.debug, args.silent)

    _check_libraries()
    _load_user_classes()

    if args.abilities:
        show_abilities()
        return

    dbfile = os.path.expanduser(args.database_file)
    if args.debug and os.path.isfile('./webmon.db'):
        dbfile = "./webmon.db"
    database.DB.initialize(dbfile)

    if args.add_user:
        add_user(args.add_user)
        return

    if args.migrate_filename:
        from . import migrate
        migrate.migrate(args.migrate_filename)
        return

    cworker = worker.CheckWorker()
    cworker.start()

    web.start_app(dbfile, args.debug, args.web_app_root)


if __name__ == "__main__":
    main()
