#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" Logging setup.
Copyright (c) Karol Będkowski, 2014-2016

This file is part of exifeditor
Licence: GPLv2+
"""

import sys
import os.path
import logging
import tempfile
import time

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2014-2016"


class ColorFormatter(logging.Formatter):
    """ Formatter for logs that color messages according to level. """
    FORMAT_MAP = {level: ("\033[1;%dm%s\033[0m" % (color, level))
                  for level, color in
                  (("DEBUG", 34), ("INFO", 37), ("WARNING", 33), ("ERROR", 31),
                   ("CRITICAL", 31))}

    def format(self, record):
        record.levelname = self.FORMAT_MAP.get(record.levelname,
                                               record.levelname)
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


def logging_setup(filename, debug=False, silent=False):
    """ Setup configuration.

    Args:
        filename: optional log file name
        debug: (bool) set more messages (debug messages)
    """
    logger = logging.getLogger()
    if silent:
        logger.setLevel(logging.WARN)
    elif debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    if filename:
        log_fullpath = _create_dirs_for_log(filename)
        fileh = logging.FileHandler(log_fullpath)
        fileh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s - %(message)s"))
        logger.addHandler(fileh)

    console = logging.StreamHandler()
    fmtr = logging.Formatter
    if sys.platform != "win32":
        fmtr = ColorFormatter
    console.setFormatter(fmtr("%(levelname)-8s %(name)s - %(message)s"))
    logger.addHandler(console)

    log = logging.getLogger(__name__)
    log.debug("logging_setup() finished")
