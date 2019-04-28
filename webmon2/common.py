#!/usr/bin/python3
"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""

import copy
import logging
import itertools
import os.path
import pathlib
import time
import typing as ty

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"


_LOG = logging.getLogger("common")


class ParamError(RuntimeError):
    """Exception raised on missing param"""


class InputError(RuntimeError):
    """Exception raised on command error"""

    def __init__(self, input_=None, *args, **kwds):
        super().__init__(*args, **kwds)
        self.input = input_


class FilterError(RuntimeError):
    """Exception raised on command error"""

    def __init__(self, filter_=None, *args, **kwds):
        super().__init__(*args, **kwds)
        self.filter = filter_


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


def parse_interval(instr: ty.Union[str, float, int]) -> int:
    """Parse interval in human readable format and return interval in sec."""
    if isinstance(instr, (int, float)):
        if instr < 1:
            raise ValueError("invalid interval '%s'" % instr)
        return int(instr)

    instr = instr.lower()

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
    return character in (' ', '\t')


def get_whitespace_prefix(text: str) -> str:
    """Get all whitespace characters from beginning of `text`"""
    return ''.join(itertools.takewhile(is_whitespace, text))


def _parse_hour_min(text: str) -> int:
    hours = 0  # type: int
    minutes = 0  # type: int
    text = text.strip()
    if ':' in text:
        hours_str, minutes_str, *_ = text.split(':', 3)
        hours = int(hours_str) % 24
        minutes = int(minutes_str) % 60
    else:
        hours = int(text) % 24

    return hours * 60 + minutes


def parse_hours_range(inp: str) -> ty.Iterable[ty.Tuple[int, int]]:
    """ Parse hours ranges defined as:
        hour1[:minutes1]-hour2[:minutes](,hour1[:minutes1]-hour2[:minutes])+
    Returns iterable: (start_time, end_time) for each valid range
    start_time, end_time = int: hour * 60 + minutes
    """
    # pylint: disable=invalid-sequence-index
    inp = inp.replace(' ', '').replace('\t', '')
    for hrang in inp.split(','):
        if '-' not in hrang:
            continue
        start, stop = hrang.split('-')
        if not start or not stop:
            continue
        try:
            start_hm = _parse_hour_min(start)
            stop_hm = _parse_hour_min(stop)
            yield (start_hm, stop_hm)
        except ValueError:
            pass


def check_date_in_timerange(tsrange: str, timestamp: ty.Union[int, float]) \
        -> bool:
    """ Check is `timestamp` is one of time ranges defined in `tsrange`"""
    timestampt = time.localtime(timestamp)
    tshm = timestampt.tm_hour * 60 + timestampt.tm_min
    for rstart, rstop in parse_hours_range(tsrange):
        if rstart < rstop:
            if rstart <= tshm and tshm <= rstop:
                return True
        else:
            if not (rstop < tshm and rstart > tshm):
                return True
    return False