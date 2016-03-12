#!/usr/bin/python3

import difflib

from . import common


def context_diff(prev, fromfiledate, current, tofiledate):
    return difflib.context_diff(
        prev, current,
        fromfiledate=fromfiledate, tofiledate=tofiledate,
        lineterm='\n')


def unified_diff(prev, fromfiledate, current, tofiledate):
    return difflib.unified_diff(
        prev, current,
        fromfiledate=fromfiledate, tofiledate=tofiledate,
        lineterm='\n')


def ndiff(prev, _fromfiledate, current, _tofiledate):
    return difflib.ndiff(prev, current)


def _substract_lists(list1, list2):
    """ Get only items from list1 that not exists in list2"""
    l2set = set(list2)
    return (item for item in list1 if item not in l2set)


def added(prev, _fromfiledate, current, _tofiledate):
    """ Get only added items """
    result = _substract_lists(current, prev)
    return "\n".join(map(str, result))


def deleted(prev, _fromfiledate, current, _tofiledate):
    """ Get only deleted items """
    result = _substract_lists(prev, current)
    return "\n".join(map(str, result))


def modified(prev, _fromfiledate, current, _tofiledate):
    """ Make diff and return only modified lines. """
    def _mkdiff():
        diff = difflib.SequenceMatcher(a=prev, b=current)
        for change, _, _, begin2, end2 in diff.get_opcodes():
            if change == 'replace':
                for itm in current[begin2:end2]:
                    yield itm

    return "\n".join(_mkdiff())


def last(_prev, _fromfiledate, current, _tofiledate):
    """ Return last (current) version """
    return current


_COMPARATORS = {
    "context": context_diff,
    "unified": unified_diff,
    "ndiff": ndiff,
    "added": added,
    "deleted": deleted,
    "modified": modified,
    "last": last,
}


def get_comparator(name):
    cmpf = _COMPARATORS.get(name)
    if not cmpf:
        raise common.ParamError("Unknown comparator: %s" % name)
    return cmpf
