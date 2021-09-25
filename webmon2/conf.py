#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2021 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Application configuration.
"""
import configparser
import logging
import os
import typing as ty

_LOG = logging.getLogger("conf")

_DEFAULTS = """
[main]
workers = 2
database = postgresql://webmon2:webmon2@127.0.0.1:5432/webmon2

[web]
address = 127.0.0.1
port = 5000
root = /

[smtp]
enabled = False
address = 127.0.0.1
port = 25
ssl = false
starttls = false
login =
password =
from = webmon2 <webmon2@localhost>
"""


def load_conf(fileobj):
    conf = configparser.ConfigParser()
    conf.read_string(_DEFAULTS)
    conf.read_file(fileobj)
    return conf


def try_load_user_conf():
    user_conf = os.path.expanduser("~/.config/webmon2/webmon2.ini")
    if os.path.isfile(user_conf):
        try:
            _LOG.info("loading %s", user_conf)
            with open(user_conf) as fileobj:
                return load_conf(fileobj)
        except:
            _LOG.exception("load file %s error", user_conf)

    return None


def default_conf():
    conf = configparser.ConfigParser()
    conf.read_string(_DEFAULTS)
    return conf


def update_from_args(conf, args):
    if args.database:
        conf.set("main", "database", args.database)

    if args.cmd == "serve":
        if args.web_app_root:
            conf.set("web", "root", args.web_app_root)

        if args.web_address:
            conf.set("web", "address", args.web_address)
        if args.web_port:
            conf.set("web", "port", str(args.web_port))

        if args.workers:
            conf.set("main", "workers", str(args.workers))

        if args.smtp_server_address:
            conf.set("smtp", "address", args.smtp_server_address)
            conf.set("smtp", "enabled", str(True))

        if args.smtp_server_port:
            conf.set("smtp", "port", str(args.smtp_server_port))

        if args.smtp_server_ssl:
            conf.set("smtp", "ssl", str(args.smtp_server_ssl))

        if args.smtp_server_starttls:
            conf.set("smtp", "starttls", str(args.smtp_server_starttls))

        if args.smtp_server_from:
            conf.set("smtp", "from", args.smtp_server_from)

        if args.smtp_server_login:
            conf.set("smtp", "login", args.smtp_server_login)

        if args.smtp_server_password:
            conf.set("smtp", "password", args.smtp_server_password)

    return conf


def validate(conf) -> bool:
    valid = True

    if not conf.get("web", "root"):
        _LOG.error("Invalid web root")
        valid = False

    web_address = conf.get("web", "address")
    if not web_address:
        _LOG.error("Invalid web address")
        valid = False

    try:
        web_port = int(conf.get("web", "port"))
    except ValueError:
        _LOG.error("Invalid web port")
        valid = False
    else:
        if web_port < 1 or web_port > 65535:
            _LOG.error("Invalid web port")
            valid = False

    if not conf.get("main", "database"):
        _LOG.error("Missing database configuration")
        valid = False

    try:
        workers = int(conf.get("main", "workers"))
    except ValueError:
        _LOG.error("Invalid workers parameter")
        valid = False
    else:
        if workers < 1:
            _LOG.error("Invalid workers parameter")
            valid = False

    if conf.getboolean("smtp", "enabled"):
        if not conf.get("smtp", "address"):
            _LOG.error("SMTP enabled but SMTP address is missing")
            valid = False

        try:
            port = int(conf.get("smtp", "port"))
        except ValueError:
            _LOG.error("Invalid SMTP port")
            valid = False
        else:
            if port < 1 or port > 65535:
                _LOG.error("Invalid SMTP port")
                valid = False

        if not conf.get("smtp", "from"):
            _LOG.error("Missing SMTP 'from' address")
            valid = False

    return valid


def conf_items(conf):
    for sec in conf.sections():
        yield "[" + sec + "]"
        for key, val in conf.items(sec):
            yield key + " = '" + val + "'"
        yield ""


def save_conf(conf, filename):
    with open(filename, "w") as ofile:
        conf.write(ofile)
