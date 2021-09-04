#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Logging setup.
Copyright (c) Karol Będkowski, 2014-2019

This file is part of webmon.
Licence: GPLv2+
"""

import logging
import os.path
import sys
import tempfile
import time

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"


class ColorFormatter(logging.Formatter):
    """Formatter for logs that color messages according to level."""

    FORMAT_MAP = {
        level: ("\033[1;%dm%-8s\033[0m" % (color, level))
        for level, color in (
            ("DEBUG", 34),
            ("INFO", 37),
            ("WARNING", 33),
            ("ERROR", 31),
            ("CRITICAL", 31),
        )
    }

    def format(self, record):
        record.levelname = self.FORMAT_MAP.get(
            record.levelname, record.levelname
        )
        return logging.Formatter.format(self, record)


def _create_dirs_for_log(filename):
    log_fullpath = os.path.abspath(filename)
    log_dir = os.path.dirname(log_fullpath)
    log_dir_access = os.access(log_dir, os.W_OK)

    create_temp = False
    if os.path.isabs(filename):
        if not log_dir_access:
            create_temp = True

    if create_temp:
        basename = os.path.basename(filename)
        spfname = os.path.splitext(basename)
        filename = spfname[0] + "_" + str(int(time.time())) + spfname[1]
        log_fullpath = os.path.join(tempfile.gettempdir(), filename)
    return log_fullpath


def setup(filename, debug=False, silent=False):
    """Setup logging.

    Args:
    :param filename: (str, optional) log file name
    :param debug: (bool) run in debug mode (all messages)
    :param silent: (bool) show only warnings/errors
    """
    logger = logging.getLogger()
    log_req = logging.getLogger("requests")
    log_github3 = logging.getLogger("github3")

    if debug:
        logger.setLevel(logging.DEBUG)
        log_req.setLevel(logging.DEBUG)
        log_github3.setLevel(logging.DEBUG)
    elif silent:
        logger.setLevel(logging.WARN)
        log_req.setLevel(logging.WARN)
        log_github3.setLevel(logging.WARN)
    else:
        logger.setLevel(logging.INFO)
        log_req.setLevel(logging.WARN)
        log_github3.setLevel(logging.WARN)

    if filename:
        log_fullpath = _create_dirs_for_log(filename)
        fileh = logging.FileHandler(log_fullpath)
        fileh.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
            )
        )
        logger.addHandler(fileh)

    console = logging.StreamHandler()
    fmtr = logging.Formatter
    if sys.platform != "win32" and debug:
        fmtr = ColorFormatter

    console.setFormatter(fmtr("%(levelname)-8s %(name)s - %(message)s"))
    logger.addHandler(console)

    log = logging.getLogger("logging")
    log.debug("logging_setup() finished")
