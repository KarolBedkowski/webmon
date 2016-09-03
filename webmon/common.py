#!/usr/bin/python3
"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import copy
import logging
import os.path
import pathlib
import pprint
import typing as ty

import typecheck as tc

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


def find_subclass(base_class, name: str):
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


@tc.typecheck
def parse_interval(instr: str) -> int:
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

    def __init__(self, conf: dict, gcache, idx: int, output, args) -> None:
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
        }  # type: Dict[str, ty.Any]

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


class Result(object):
    FIELDS = ['title', 'link']

    def __init__(self, oid: str) -> None:
        self.oid = oid  # type: str
        self.title = None  # type: str
        self.link = None  # type: str
        self.items = []  # type: List[str]
        # debug informations related to this result
        self.debug = {}  # type: Dict[str, ty.Any]
        # metadata related to this result
        self.meta = {
            "status": None,
            "update_duration": 0,
            "error": None,
            "update_date": None,
        }  # type: Dict[str, ty.Any]

    def __str__(self):
        return "<Result: " + pprint.saferepr(self.__dict__) + ">"

    def clone(self):
        return copy.deepcopy(self)

    def append(self, item: str):
        self.items.append(item)
        return self

    def set_error(self, message: ty.Any):
        self.meta['status'] = STATUS_ERROR
        self.meta['error'] = str(message)
        return self

    def set_no_modified(self):
        self.meta['status'] = STATUS_UNCHANGED
        return self

    def validate(self) -> None:
        assert bool(self.oid)
        assert bool(self.title)
        assert self.meta['status'] and self.meta['status'] in (
            STATUS_NEW, STATUS_ERROR, STATUS_UNCHANGED, STATUS_CHANGED)

    def format(self) -> str:
        """ Return formatted result. """
        return "\n\n".join(self.items)


@tc.typecheck
def apply_defaults(defaults: dict, conf: dict) -> ty.Dict[str, ty.Any]:
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


@tc.typecheck
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
