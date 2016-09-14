#!/usr/bin/python3
"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import copy
import logging
import itertools
import os.path
import pathlib
import pprint
import time
import typing as ty

import typecheck as tc

from . import config

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"


_LOG = logging.getLogger("common")

# options
OPTS_PREFORMATTED = "preformatted"  # type: str


RECORD_SEPARATOR = '\x1e'  # type: str


class ParamError(RuntimeError):
    """Exception raised on missing param"""


class InputError(RuntimeError):
    """Exception raised on command error"""

    def __init__(self, input_=None, *args, **kwds):
        super(InputError, self).__init__(*args, **kwds)
        self.input = input_


class FilterError(RuntimeError):
    """Exception raised on command error"""

    def __init__(self, filter_=None, *args, **kwds):
        super(FilterError, self).__init__(*args, **kwds)
        self.filter = filter_


class ReportGenerateError(RuntimeError):
    """Exception raised on generate report error"""

    def __init__(self, generator=None, *args, **kwds):
        super(ReportGenerateError, self).__init__(*args, **kwds)
        self.generator = generator


class CacheError(RuntimeError):
    """Exception raised on command error"""

    def __init__(self, operation, fname, *args, **kwds):
        super(CacheError, self).__init__(*args, **kwds)
        self.operation = operation
        self.fname = fname


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
def parse_interval(instr: ty.Union[str, float, int, None]) -> int:
    """Parse interval in human readable format and return interval in sec."""
    if isinstance(instr, (int, float)):
        if instr < 1:
            raise ValueError("invalid interval '%s'" % instr)
        return int(instr)

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
    def debug(self) -> bool:
        return self.args.debug if self.args else None

    def _set_last_update(self, update_date: int):
        self.metadata['update_date'] = update_date

    def _get_last_update(self) -> ty.Union[float, int, None]:
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

    def __init__(self, oid: str, idx: int=0) -> None:
        self.index = idx  # type: int
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
        # result footer to print
        self.footer = None  # type: ty.Optional[str]
        self.header = None  # type: ty.Optional[str]

    def __str__(self):
        return "<Result: " + pprint.saferepr(self.__dict__) + ">"

    def clone(self):
        return copy.deepcopy(self)

    @tc.typecheck
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
        return RECORD_SEPARATOR.join(self.items)


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

    pathlib.Path(path).mkdir(parents=True)


def is_whitespace(character: str) -> bool:
    return character == ' ' or character == '\t'


@tc.typecheck
def get_whitespace_prefix(text: str) -> str:
    """Get all whitespace characters from beginning of `text`"""
    return ''.join(itertools.takewhile(is_whitespace, text))


@tc.typecheck
def prepare_filename(base_name: str) -> str:
    if not base_name:
        _LOG.warning("prepare_filename - empty base name")
        return base_name
    # replace time tags
    name = time.strftime(base_name)
    # replace ~
    name = os.path.expanduser(name)
    return name
