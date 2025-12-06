# Copyright © 2021 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Application configuration.
"""

from __future__ import annotations

import ipaddress
import typing as ty
from configparser import ConfigParser
from pathlib import Path

import structlog

if ty.TYPE_CHECKING:
    import argparse

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger("conf")

_DEFAULTS = """
[main]
workers = 2
database = postgresql://webmon2:webmon2@127.0.0.1:5432/webmon2
db_pool_min = 2
db_pool_max = 20
work_interval = 300
internet_check_url =

[web]
address = 127.0.0.1
port = 5000
root = /
minify = false
pool = 20
proxy_media = false

[smtp]
enabled = False
address = 127.0.0.1
port = 25
ssl = false
starttls = false
login =
password =
from = webmon2 <webmon2@localhost>

[metrics]
# comma separated accepted client ip
allow_from = 127.0.0.1
"""


def load_conf(fileobj: ty.Iterable[str]) -> ConfigParser:
    conf = ConfigParser()
    conf.read_string(_DEFAULTS)
    conf.read_file(fileobj)
    return conf


def try_load_user_conf() -> ConfigParser | None:
    user_conf = Path("~/.config/webmon2/webmon2.ini").expanduser()
    if Path(user_conf).is_file():
        try:
            _LOG.info("conf: loading from %s", user_conf)
            with user_conf.open(encoding="UTF-8") as fileobj:
                return load_conf(fileobj)

        # pylint: disable=broad-except
        except Exception as err:
            _LOG.exception("conf: load file %s error", user_conf, error=err)

    return None


def default_conf() -> ConfigParser:
    conf = ConfigParser()
    conf.read_string(_DEFAULTS)
    return conf


def _update_from_args_smtp(
    conf: ConfigParser, args: argparse.Namespace
) -> None:
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


# pylint: disable=too-many-branches
def update_from_args(
    conf: ConfigParser, args: argparse.Namespace
) -> ConfigParser:
    if args.database:
        conf.set("main", "database", args.database)

    if args.cmd == "serve":
        if args.web_app_root:
            conf.set("web", "root", args.web_app_root)

        if args.web_address:
            conf.set("web", "address", args.web_address)
        if args.web_port:
            conf.set("web", "port", str(args.web_port))

        if args.workers is not None:
            conf.set("main", "workers", str(args.workers))

        _update_from_args_smtp(conf, args)

    return conf


# pylint: disable=too-many-branches
def validate(conf: ConfigParser) -> bool:
    # validate all sections
    valid_web = _validate_web(conf)
    valid_main = _validate_main(conf)
    valid_smtp = _validate_smtp(conf)
    valid_metrics = _validate_metrics(conf)
    return valid_web and valid_main and valid_smtp and valid_metrics


def _validate_web(conf: ConfigParser) -> bool:
    valid = True

    if not conf.get("web", "root"):
        _LOG.error("conf: missing web root")
        valid = False

    if not conf.get("web", "address"):
        _LOG.error("conf: missing web address")
        valid = False

    try:
        web_port = int(conf.get("web", "port"))
    except ValueError as err:
        _LOG.error("conf: invalid or missing web port", error=err)
        valid = False
    else:
        if web_port < 1 or web_port > 65535:  # noqa:PLR2004
            _LOG.error("conf: invalid web port: %r", web_port)
            valid = False

    return valid


def _validate_main(conf: ConfigParser) -> bool:
    valid = True

    if not conf.get("main", "database"):
        _LOG.error("conf: missing database configuration")
        valid = False

    try:
        if (workers := int(conf.get("main", "workers"))) < 1:
            _LOG.warning("conf: number of workers: %r", workers)

    except ValueError as err:
        _LOG.error("conf: invalid workers parameter", error=err)
        valid = False

    try:
        work_interval = int(conf.get("main", "work_interval"))
    except ValueError as err:
        _LOG.error("conf: invalid work_interval", error=err)
        valid = False
    else:
        if work_interval < 1:
            _LOG.error(
                "conf: invalid work_interval parameter: %r",
                work_interval,
            )
            valid = False

    return valid


def _validate_smtp(conf: ConfigParser) -> bool:
    valid = True

    if conf.getboolean("smtp", "enabled"):
        if not conf.get("smtp", "address"):
            _LOG.error("conf: missing smtp address")
            valid = False

        try:
            port = int(conf.get("smtp", "port"))
        except ValueError as err:
            _LOG.error("conf: invalid SMTP port", error=err)
            valid = False
        else:
            if port < 1 or port > 65535:  # noqa:PLR2004
                _LOG.error("conf: invalid SMTP port: %r", port)
                valid = False

        if not conf.get("smtp", "from"):
            _LOG.error("conf: missing SMTP 'from' address")
            valid = False

    return valid


def _validate_metrics(conf: ConfigParser) -> bool:
    valid = True
    if allow_from := conf.get("metrics", "allow_from"):
        for a in allow_from.split(","):
            addr = a.strip()
            try:
                if "/" in addr:
                    ipaddress.ip_network(addr, strict=False)
                else:
                    ipaddress.ip_address(addr)

            except ValueError as err:
                _LOG.error(
                    "conf: metrics has invalid IP or network: %r",
                    addr,
                    error=err,
                )
                valid = False

    return valid


def conf_items(conf: ConfigParser) -> ty.Iterator[str]:
    for sec in conf.sections():
        yield "[" + sec + "]"
        for key, val in conf.items(sec):
            yield f"{key} = '{val}'"

        yield ""


def save_conf(conf: ConfigParser, cfgfile: Path) -> None:
    with cfgfile.open(mode="w", encoding="UTF-8") as ofile:
        conf.write(ofile)
