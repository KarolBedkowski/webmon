#!/usr/bin/python3
"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import logging

from . import config

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"


# options
OPTS_PREFORMATTED = "preformatted"


class NotModifiedError(RuntimeError):
    """Exception raised on HTTP 304 responses"""


class NotFoundError(RuntimeError):
    """Exception raised on HTTP 400 responses"""


class ParamError(RuntimeError):
    """Exception raised on missing param"""


class InputError(RuntimeError):
    """Exception raised on command error"""


class ReportGenerateError(RuntimeError):
    """Exception raised on generate report error"""


def find_subclass(base_class, name):
    """ Find subclass to given `base_class` with given value of
    attribute `name` """

    for cname, clazz in get_subclasses_with_name(base_class):
        if cname == name:
            return clazz

    return None


def get_subclasses_with_name(base_class):
    """ Iter over subclasses and yield `name` attribute """

    def find(parent_cls):
        for rcls in getattr(parent_cls, "__subclasses__")():
            name = getattr(rcls, 'name')
            if name:
                yield name, rcls
            yield from find(rcls)

    yield from find(base_class)


def parse_interval(instr):
    """Parse interval in human readable format and return interval in sec."""
    if isinstance(instr, (int, float)):
        if instr < 1:
            raise ValueError("invalid interval '%s'" % instr)
        return instr

    mplt = 1
    if instr.endswith("m"):
        mplt = 60
        instr = instr[:-1]
    elif instr.endswith("h"):
        mplt = 3600
        instr = instr[:-1]
    elif instr.endswith("d"):
        mplt = 86400
        instr = instr[:-1]
    elif instr.endswith("w"):
        mplt = 604800
        instr = instr[:-1]
    try:
        val = int(instr) * mplt
        if val < 1:
            raise ValueError()
        return val
    except ValueError:
        raise ValueError("invalid interval '%s'" % instr)


class Context(object):
    """Processing context

    TODO: czy zapisywanie powinno być do kontekstu?
    """
    _log = logging.getLogger("context")

    def __init__(self, conf, gcache, idx, output, args):
        super(Context, self).__init__()
        self.conf = conf
        self.opt = {}
        self.debug_data = {}
        self.idx = idx
        if conf:
            self.name = config.get_input_name(conf)
            self.oid = config.gen_input_oid(conf)
        else:
            self.name = "src_" + str(idx)
            self.oid = str(idx)
        self.cache = gcache
        self.output = output
        self.args = args
        self.metadata = {}
        self.last_updated = None

        self._log_prefix = "".join((
            "[",
            str(self.idx + 1), ": ", self.name,
            ("/" + self.oid) if self.debug else "",
            "] "
        ))

    @property
    def debug(self):
        return self.args.debug if self.args else None

    def __str__(self):
        return "<Context idx={} oid={} name={} conf={} opt={} debug={} "\
            "meta={}>".\
            format(self.idx, self.oid, self.name, self.conf, self.opt,
                   self.debug_data, self.metadata)

    def log_info(self, fmt, *args, **kwds):
        self._log.info(self._log_prefix + fmt, *args, **kwds)

    def log_debug(self, fmt, *args, **kwds):
        if self.debug:
            self._log.debug(self._log_prefix + fmt, *args, **kwds)

    def log_error(self, fmt, *args, **kwds):
        if self.debug:
            self._log.exception(self._log_prefix + fmt, *args, **kwds)
        else:
            self._log.error(self._log_prefix + fmt, *args, **kwds)
