#!/usr/bin/python3
"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

# replace new line character with this character
PART_LINES_SEPARATOR = "\x01"

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
