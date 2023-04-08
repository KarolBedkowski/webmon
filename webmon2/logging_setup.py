"""Logging setup.
Copyright (c) Karol Będkowski, 2014-2022

This file is part of webmon.
Licence: GPLv2+
"""

import logging
import os.path
import sys
import tempfile
import time
import typing as ty
from pathlib import Path

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2022"

_ = ty


class ColorFormatter(logging.Formatter):
    """Formatter for logs that color messages according to level."""

    FORMAT_MAP = {
        levelno: f"\033[1;{color}m{level:<8}\033[0m"
        for levelno, level, color in (
            (logging.DEBUG, "DEBUG", 34),
            (logging.INFO, "INFO", 37),
            (logging.WARNING, "WARNING", 33),
            (logging.ERROR, "ERROR", 31),
            (logging.CRITICAL, "CRITICAL", 31),
        )
    }

    def format(self, record: logging.LogRecord) -> str:
        record.levelname = self.FORMAT_MAP.get(
            record.levelno, record.levelname
        )
        return logging.Formatter.format(self, record)


def _create_dirs_for_log(filename: str) -> str:
    log_fullpath = os.path.abspath(filename)
    log_dir = os.path.dirname(log_fullpath)
    log_dir_access = os.access(log_dir, os.W_OK)

    create_temp = False
    if Path(filename).is_absolute():
        if not log_dir_access:
            create_temp = True

    if create_temp:
        basename = os.path.basename(filename)
        spfname = os.path.splitext(basename)
        filename = spfname[0] + "_" + str(int(time.time())) + spfname[1]
        log_fullpath = os.path.join(tempfile.gettempdir(), filename)
    return log_fullpath


class NoMetricsLogFilter(
    logging.Filter
):  # pylint: disable=too-few-public-methods
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter that remove successful request to /metrics endpoint"""
        return (
            record.levelno != logging.INFO
            or record.name != "werkzeug"
            or '/metrics HTTP/1.1" 200' not in record.getMessage()
        )


def setup(filename: str, debug: bool = False, silent: bool = False) -> None:
    """Setup logging.

    Args:
    :param filename: (str, optional) log file name
    :param debug: (bool) run in debug mode (all messages)
    :param silent: (bool) show only warnings/errors
    """
    logger = logging.getLogger()
    log_req = logging.getLogger("requests")
    log_github3 = logging.getLogger("github3")
    log_werkzeug = logging.getLogger("werkzeug")

    msg_format = (
        "%(levelname)-8s %(name)s [%(filename)s:%(lineno)d] %(message)s"
    )
    if debug:
        logger.setLevel(logging.DEBUG)
        log_req.setLevel(logging.DEBUG)
        log_github3.setLevel(logging.DEBUG)
        log_werkzeug.setLevel(logging.DEBUG)
    elif silent:
        logger.setLevel(logging.WARN)
        log_req.setLevel(logging.WARN)
        log_github3.setLevel(logging.WARN)
        logger.addFilter(NoMetricsLogFilter())
        log_werkzeug.addFilter(NoMetricsLogFilter())
    else:
        logger.setLevel(logging.INFO)
        log_req.setLevel(logging.WARN)
        log_github3.setLevel(logging.WARN)
        logger.addFilter(NoMetricsLogFilter())
        log_werkzeug.addFilter(NoMetricsLogFilter())

    if filename:
        log_fullpath = _create_dirs_for_log(filename)
        fileh = logging.FileHandler(log_fullpath)
        fileh.setFormatter(logging.Formatter("%(asctime)s " + msg_format))
        logger.addHandler(fileh)

    console = logging.StreamHandler()
    fmtr = logging.Formatter
    if sys.platform != "win32" and debug:
        fmtr = ColorFormatter

    console.setFormatter(fmtr(msg_format))
    logger.addHandler(console)

    log = logging.getLogger("logging")
    log.debug("logging_setup() finished")
