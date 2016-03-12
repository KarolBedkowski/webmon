#!/usr/bin/python3
"""
Commons elements - errors etc
"""


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

    def find(parent_cls):
        for rcls in getattr(parent_cls, "__subclasses__")():
            if getattr(rcls, 'name') == name:
                return rcls
            out = find(rcls)
            if out:
                return out
        return None

    return find(base_class)
