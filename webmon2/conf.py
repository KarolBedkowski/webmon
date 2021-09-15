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
import os
import logging
import typing as ty
import yaml

_LOG = logging.getLogger("conf")


def load_conf(filename):
    if os.path.isfile(filename):
        with open(filename) as fconf:
            return yaml.safe_load(fconf)

    _LOG.debug("config file %s not found", filename)
    return None


def default_conf():
    return {
        "web": {
            "address": "127.0.0.1:5000",
            "root": "/",
        },
        "workers": 2,
        "database": None,
        "smtp": {
            "enabled": False,
            "address": None,
            "port": 25,
            "ssl": False,
            "starttls": False,
            "from": None,
            "login": None,
            "password": None,
        },
    }


def update_from_args(conf, args):
    if args.database:
        conf["database"] = args.database

    if args.web_app_root:
        conf["web"]["root"] = args.web_app_root

    if args.web_address:
        conf["web"]["address"] = args.web_address

    if args.workers:
        conf["workers"] = args.workers

    if args.smtp_server_address:
        conf["smtp"]["address"] = args.smtp_server_address
        conf["smtp"]["enabled"] = True

    if args.smtp_server_port:
        conf["smtp"]["port"] = args.smtp_server_port

    if args.smtp_server_ssl:
        conf["smtp"]["ssl"] = args.smtp_server_ssl

    if args.smtp_server_starttls:
        conf["smtp"]["starttls"] = args.smtp_server_starttls

    if args.smtp_server_from:
        conf["smtp"]["from"] = args.smtp_server_from

    if args.smtp_server_login:
        conf["smtp"]["login"] = args.smtp_server_login

    if args.smtp_server_password:
        conf["smtp"]["password"] = args.smtp_server_password

    return conf


def validate(conf: ty.Dict) -> bool:
    valid = True

    web = conf["web"]
    if not web["root"]:
        _LOG.error("Invalid web root")
        valid = False

    if not web["address"] or not ":" in web["address"]:
        _LOG.error("Invalid web address")
        valid = False

    if not conf["database"]:
        _LOG.error("Missing database configuration")
        valid = False

    try:
        workers = int(conf["workers"])
    except ValueError:
        _LOG.error("Invalid workers parameter")
        valid = False
    else:
        if workers < 1:
            _LOG.error("Invalid workers parameter")
            valid = False

    smtp = conf["smtp"]
    if smtp["enabled"]:
        if not smtp["address"]:
            _LOG.error("SMTP enabled but SMTP address is missing")
            valid = False

        try:
            port = int(smtp["port"])
        except ValueError:
            _LOG.error("Invalid SMTP port")
            valid = False
        else:
            if port < 1 or port > 65535:
                _LOG.error("Invalid SMTP port")
                valid = False

        if not smtp["from"]:
            _LOG.error("Missing SMTP 'from' address")
            valid = False

    return valid
