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


from . import database, logging_setup, worker, web, cli, conf

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2021"
_ = ty

VERSION = "2.5.1"
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
        help="show additional information",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="print debug information"
    )
    parser.add_argument("--log", help="log file name")

    parser.add_argument(
        "-c",
        "--conf",
        type=argparse.FileType("r"),
        help="configuration file name",
        dest="conf",
    )
    parser.add_argument(
        "--database",
        help="database connection string",
    )

    subparsers = parser.add_subparsers(help="Commands", dest="cmd")
    subparsers.add_parser(
        "abilities", help="show available filters/sources/comparators"
    )

    subparsers.add_parser("update-schema", help="update database schema")

    parser_mig = subparsers.add_parser(
        "migrate", help="migrate sources from file"
    )
    parser_mig.add_argument(
        "-f",
        "--filename",
        help="migrate sources from file",
        dest="migrate_filename",
    )

    parser_users = subparsers.add_parser("users", help="manage users")

    parser_users_sc = parser_users.add_subparsers(
        help="user commands", dest="subcmd", required=True
    )

    parser_users_add = parser_users_sc.add_parser("add", help="add user")
    parser_users_add.add_argument("-l" "--login", required=True)
    parser_users_add.add_argument("-p" "--password", required=True)
    parser_users_add.add_argument(
        "--admin",
        action="store_true",
        default=False,
        help="set admin role for user",
    )

    parser_users_cp = parser_users_sc.add_parser(
        "passwd", help="change user password"
    )
    parser_users_cp.add_argument("-l" "--login", required=True)
    parser_users_cp.add_argument("-p" "--password", required=True)

    parser_users_rtotp = parser_users_sc.add_parser(
        "remove_totp", help="remove two factor authentication for user"
    )
    parser_users_rtotp.add_argument("-l" "--login", required=True)

    parser_serve = subparsers.add_parser("serve", help="Start application")

    parser_serve.add_argument(
        "--app-root",
        help="root for url patch (for reverse proxy)",
        dest="web_app_root",
    )
    parser_serve.add_argument(
        "--workers", type=int, default=2, help="number of background workers"
    )
    parser_serve.add_argument(
        "--address",
        type=str,
        help="web interface listen address",
        dest="web_address",
    )
    parser_serve.add_argument(
        "--port",
        type=str,
        help="web interface listen port",
        dest="web_port",
    )
    parser_serve.add_argument(
        "--smtp-server-address",
        help="smtp server address",
        dest="smtp_server_address",
    )
    parser_serve.add_argument(
        "--smtp-server-port", help="smtp server port", dest="smtp_server_port"
    )
    parser_serve.add_argument(
        "--smtp-server-ssl",
        help="enable ssl for smtp serve",
        action="store_true",
        dest="smtp_server_ssl",
    )
    parser_serve.add_argument(
        "--smtp-server-starttls",
        help="enable starttls for smtp serve",
        action="store_true",
        dest="smtp_server_starttls",
    )
    parser_serve.add_argument(
        "--smtp-server-from",
        help="email address for webmon",
        dest="smtp_server_from",
    )
    parser_serve.add_argument(
        "--smtp-server-login",
        help="login for smtp authentication",
        dest="smtp_server_login",
    )
    parser_serve.add_argument(
        "--smtp-server-password",
        help="password for smtp authentication",
        dest="smtp_server_password",
    )

    parser_wc = subparsers.add_parser(
        "write-config", help="write default configuration file"
    )
    parser_wc.add_argument(
        "-f",
        "--filename",
        help="destination filename",
        default="~/.config/webmon2/webmon2.ini",
        dest="conf_filename",
        required=True,
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

    if args.cmd == "abilities":
        cli.show_abilities()
        return

    app_conf = None
    if args.conf:
        app_conf = conf.load_conf(args.conf)
    else:
        app_conf = conf.try_load_user_conf()

    if not app_conf:
        _LOG.debug("loading default conf")
        app_conf = conf.default_conf()

    app_conf = conf.update_from_args(app_conf, args)
    _LOG.debug("app_conf: %r", "  ".join(conf.conf_items(app_conf)))
    if not conf.validate(app_conf):
        _LOG.error("app_conf validation error")
        return

    if args.cmd == "update-schema":
        if is_running_from_reloader():
            _LOG.error("cannot update schema when running from reloader")
        else:
            _LOG.info("update schema...")
            database.DB.initialize(app_conf.get("main", "database"), True)
        return

    database.DB.initialize(app_conf.get("main", "database"), False)

    if cli.process_cli(args, app_conf):
        return

    if args.cmd == "serve":
        if not is_running_from_reloader():
            cworker = worker.CheckWorker(app_conf, debug=args.debug)
            cworker.start()

        web.start_app(args, app_conf)
        return

    _LOG.error("missing command")


if __name__ == "__main__":
    main()
