#!/usr/bin/python3
"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import logging
import copy
import os.path
import pathlib
import pprint

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
    """
    _log = logging.getLogger("context")

    def __init__(self, conf, gcache, idx, output, args):
        super(Context, self).__init__()
        # input configuration
        self.input_conf = conf
        # input configuration idx
        self.input_idx = idx
        if conf:
            self.name = config.get_input_name(conf, idx)
            self.oid = config.gen_input_oid(conf)
        else:
            self.name = "src_" + str(idx)
            self.oid = str(idx)
        # cache manager
        self.cache = gcache
        # output manager
        self.output = output
        # app arguments
        self.args = args
        # last loader metadata
        self.metadata = {
            'update_date': None,
            'last_error': None,
            'last_error_msg': None,
            'status': None,
        }

        self._log_prefix = "".join((
            "[",
            str(idx + 1), ": ", self.name,
            ("/" + self.oid) if self.debug else "",
            "] "
        ))

    @property
    def debug(self):
        return self.args.debug if self.args else None

    def _set_last_update(self, update_date: int):
        self.metadata['update_date'] = update_date

    def _get_last_update(self):
        return self.metadata.get('update_date')

    last_updated = property(_get_last_update, _set_last_update)

    def __str__(self):
        return "<Context idx={} oid={} name={} input_conf={} meta={}>".\
            format(self.input_idx, self.oid, self.name, self.input_conf,
                   self.metadata)

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


STATUS_NEW = 'new'
STATUS_CHANGED = 'chg'
STATUS_UNCHANGED = 'ucg'
STATUS_ERROR = 'err'

STATUSES = {
    STATUS_NEW: 'new',
    STATUS_CHANGED: 'changed',
    STATUS_UNCHANGED: 'unchanged',
    STATUS_ERROR: 'error',
}


def status_human_str(status: str) -> str:
    return STATUSES.get(status, status)


class Item(object):
    """docstring for Item"""
    FIELDS = ['title', 'date', 'link', 'author', 'content']

    def __init__(self, content=None):
        super(Item, self).__init__()
        self.title = None
        self.date = None
        self.link = None
        self.author = None
        self.content = content

    def __lt__(self, other):
        return [getattr(self, key) for key in self.FIELDS] < \
            [getattr(other, key) for key in self.FIELDS]

    def __eq__(self, other):
        return [getattr(self, key) for key in self.FIELDS] == \
            [getattr(other, key) for key in self.FIELDS]

    def copy(self, **kwargs):
        cpy = Item()
        for field in self.FIELDS:
            setattr(cpy, field, getattr(self, field))
        for key, val in kwargs.items():
            setattr(cpy, key, val)
        return cpy


class Result(object):
    FIELDS = ['title', 'link']

    def __init__(self, oid: str):
        self.oid = oid  # type: str
        self.title = None  # type: str
        self.link = None  # type: str
        self.items = []  # type: [Item]
        # debug informations related to this result
        self.debug = {}  # type: dict
        # metadata related to this result
        self.meta = {
            "status": None,
            "update_duration": 0,
            "error": None,
            "update_date": None,
        }  # type: dict

    def __str__(self):
        return "<Result: " + pprint.saferepr(self.__dict__) + ">"

    def append(self, item):
        self.items.append(item)
        return self

    def append_simple_text(self, content):
        self.items.append(Item(content))
        return self

    def set_error(self, message):
        self.meta['status'] = STATUS_ERROR
        self.meta['error'] = str(message)
        return self

    def set_no_modified(self):
        self.meta['status'] = STATUS_UNCHANGED
        return self

    def validate(self):
        assert bool(self.oid)
        assert bool(self.title)
        assert self.meta['status'] and self.meta['status'] in (
            STATUS_NEW, STATUS_ERROR, STATUS_UNCHANGED, STATUS_CHANGED)


def apply_defaults(defaults: dict, conf: dict) -> dict:
    """Deep copy & update `defaults` dict with `conf`."""
    result = copy.deepcopy(defaults)

    def update(dst, src):
        for key, val in src.items():
            if isinstance(val, dict):
                if key not in dst:
                    dst[key] = {}
                update(dst[key], val)
            else:
                dst[key] = copy.deepcopy(val)

    if conf:
        update(result, conf)

    return result


def create_missing_dir(path: str):
    """ Check path and if not exists create directory.
        If path exists and is not directory - raise error.
    """
    path = os.path.expanduser(path)
    if os.path.exists(path):
        if os.path.isdir(path):
            return
        raise RuntimeError("path {} exists and is not dir".format(path))

    try:
        pathlib.Path(path).mkdir(parents=True)
    except IOError as err:
        raise RuntimeError("creating {} error: {}".format(
            path, str(err)))
