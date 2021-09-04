#!/usr/bin/python3
"""
Main functions.

Copyright (c) Karol Będkowski, 2016-2021

This file is part of webmon.
Licence: GPLv2+
"""

import argparse
import imp
import locale
import logging
import os.path
import typing as ty

from werkzeug.serving import is_running_from_reloader

try:
    import stackprinter

    stackprinter.set_excepthook(style="color")
except ImportError:
    print("no stackprinter")
    try:
        from rich.traceback import install

        install()
    except ImportError:
        print("no rich.trackback")


from . import database, logging_setup, worker, web, cli

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2021"
_ = ty

VERSION = "2.2"
APP_NAME = "webmon2"

_LOG = logging.getLogger("main")
_DEFAULT_DB_FILE = "~/.local/share/" + APP_NAME + "/" + APP_NAME + ".db"


def _parse_options():
    parser = argparse.ArgumentParser(description=APP_NAME + " " + VERSION)
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        help="show only errors and warnings",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show additional informations",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="print debug informations"
    )
    parser.add_argument("--log", help="log file name")
    parser.add_argument(
        "--abilities",
        action="store_true",
        help="show available filters/sources" "comparators",
    )
    parser.add_argument(
        "--database",
        default="postgresql://webmon2:webmon2@" "127.0.0.1:5432/webmon2",
        help="database connection string",
    )
    parser.add_argument(
        "--migrate", help="migrate sources from file", dest="migrate_filename"
    )
    parser.add_argument(
        "--add-user",
        help="add user; arguments in form " "<login>:<password>[:admin]",
        dest="add_user",
    )
    parser.add_argument(
        "--change-user-password",
        help="change user password; arguments in form " "<login>:<password>",
        dest="change_user_pass",
    )
    parser.add_argument(
        "--remove-user-totp",
        help="remove 2 factor authentication for user",
        dest="remove_user_totp",
    )
    parser.add_argument(
        "--web-app-root",
        help="root for url patch (for reverse proxy)",
        default="/",
    )
    parser.add_argument(
        "--workers", type=int, default=2, help="number of background workers"
    )
    parser.add_argument(
        "--web-address",
        type=str,
        default="127.0.0.1:5000",
        help="web interface listen address",
        dest="web_address",
    )
    return parser.parse_args()


def _load_user_classes():
    users_scripts_dir = os.path.expanduser("~/.local/share/" + APP_NAME)
    if not os.path.isdir(users_scripts_dir):
        return

    for fname in os.listdir(users_scripts_dir):
        fpath = os.path.join(users_scripts_dir, fname)
        if (
            os.path.isfile(fpath)
            and fname.endswith(".py")
            and not fname.startswith("_")
        ):
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
        import markdown2
    except ImportError:
        _LOG.warn("missing markdown2 library")
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
        cli.show_abilities()
        return

    database.DB.initialize(
        args.database, update_schema=not is_running_from_reloader()
    )

    if cli.process_cli(args):
        return

    if not is_running_from_reloader():
        cworker = worker.CheckWorker(args.workers, debug=args.debug)
        cworker.start()

    web.start_app(args)


if __name__ == "__main__":
    main()
