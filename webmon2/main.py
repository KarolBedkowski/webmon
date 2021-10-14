#!/usr/bin/python3
"""
Main functions.

Copyright (c) Karol Będkowski, 2016-2021

This file is part of webmon.
Licence: GPLv2+
"""

import argparse
import importlib.util
import locale
import logging
import os.path
import signal
import sys
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

try:
    import sdnotify

    HAS_SDNOTIFY = True
except ImportError:
    HAS_SDNOTIFY = False

from . import cli, conf, database, logging_setup, web, worker

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2021"
_ = ty

VERSION = "2.5.10"
APP_NAME = "webmon2"

_LOG = logging.getLogger("main")
_DEFAULT_DB_FILE = "~/.local/share/" + APP_NAME + "/" + APP_NAME + ".db"
_SDN = sdnotify.SystemdNotifier() if HAS_SDNOTIFY else None
_SDN_WATCHDOG_INTERVAL = 15


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
    subparsers.add_parser("shell", help="launch IPython shell")

    parser_mig = subparsers.add_parser(
        "migrate", help="migrate sources from file"
    )
    parser_mig.add_argument(
        "-f",
        "--filename",
        help="migrate sources from file",
        dest="migrate_filename",
        required=True,
    )
    parser_mig.add_argument(
        "-u",
        "--user",
        help="target user login",
        dest="migrate_user",
        required=True,
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
            modname = fname[:-3]
            try:
                spec = importlib.util.spec_from_file_location(modname, fpath)
                module = importlib.util.module_from_spec(spec)
                sys.modules[modname] = module
                spec.loader.exec_module(module)

            except ImportError as err:
                _LOG.error("Importing '%s' error %s", fpath, err)


def _check_libraries():
    # pylint: disable=unused-import,import-outside-toplevel
    # pylint: disable=c-extension-no-member
    try:
        from lxml import etree

        _LOG.debug("etree version: %s", etree.__version__)
    except ImportError:
        _LOG.warning("missing lxml library")
    try:
        import cssselect

        _LOG.debug("cssselect version: %s", cssselect.__version__)
    except ImportError:
        _LOG.warning("missing cssselect library")
    try:
        import html2text

        _LOG.debug("html2text version: %s", html2text.__version__)
    except ImportError:
        _LOG.warning("missing html2text library")
    try:
        import markdown2

        _LOG.debug("markdown2 version: %s", markdown2.__version__)
    except ImportError:
        _LOG.warning("missing markdown2 library")
    try:
        import yaml

        _LOG.debug("yaml version: %s", yaml.__version__)
    except ImportError:
        _LOG.warning("missing yaml library")
    try:
        import requests

        _LOG.debug("requests version: %s", requests.__version__)
    except ImportError:
        _LOG.warning("missing requests library")
    try:
        import feedparser

        _LOG.debug("feedparser version: %s", feedparser.__version__)
    except ImportError:
        _LOG.warning("missing feedparser library")
    try:
        import github3

        _LOG.debug("github3.py version: %s", github3.__version__)
    except ImportError:
        _LOG.warning("missing github3 library")

    try:
        import flask_minify

        _LOG.debug("flask_minify version: %s", flask_minify.__version__)
    except ImportError:
        _LOG.warning("missing optional flask_minify library")


def _sd_watchdog(_signal, _frame):
    _SDN.notify("WATCHDOG=1")
    signal.alarm(_SDN_WATCHDOG_INTERVAL)


def _load_conf(args):
    if args.conf:
        app_conf = conf.load_conf(args.conf)
    else:
        app_conf = conf.try_load_user_conf()

    if not app_conf:
        _LOG.debug("loading default conf")
        app_conf = conf.default_conf()

    app_conf = conf.update_from_args(app_conf, args)
    _LOG.debug("app_conf: %r", "  ".join(conf.conf_items(app_conf)))
    return app_conf


def _serve(args, app_conf):
    if not is_running_from_reloader():
        if HAS_SDNOTIFY:
            _SDN.notify("STATUS=starting workers")

        cworker = worker.CheckWorker(app_conf, debug=args.debug)
        cworker.start()

    if HAS_SDNOTIFY:
        _SDN.notify("STATUS=running")
        _SDN.notify("READY=1")

    try:
        web.start_app(args, app_conf)
    except Exception as err:  # pylint: disable=broad-except
        _LOG.error("start app error: %s", err)

    if HAS_SDNOTIFY:
        _SDN.notify("STOPPING=1")


def _update_schema(app_conf):
    if is_running_from_reloader():
        _LOG.error("cannot update schema when running from reloader")
    else:
        _LOG.info("update schema...")
        database.DB.initialize(app_conf.get("main", "database"), True, 1, 5)


def main():
    """Main function."""

    if HAS_SDNOTIFY:
        _SDN.notify("STATUS=starting")
        signal.signal(signal.SIGALRM, _sd_watchdog)
        signal.alarm(_SDN_WATCHDOG_INTERVAL)

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

    app_conf = _load_conf(args)
    if not conf.validate(app_conf):
        _LOG.error("app_conf validation error")
        return

    if args.cmd == "update-schema":
        _update_schema(app_conf)
        return

    if HAS_SDNOTIFY:
        _SDN.notify("STATUS=init-db")

    database.DB.initialize(
        app_conf.get("main", "database"),
        False,
        app_conf.getint("main", "db_pool_min", fallback=2),
        app_conf.getint("main", "db_pool_max", fallback=20),
    )

    if cli.process_cli(args, app_conf):
        return

    if args.cmd == "serve":
        _serve(args, app_conf)
        return

    _LOG.error("missing command")


if __name__ == "__main__":
    main()
