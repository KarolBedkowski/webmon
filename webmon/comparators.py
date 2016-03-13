#!/usr/bin/python3

import difflib

from . import common


class AbstractComparator(object):
    """Abstract / base class for all comparators.
    Comparator get two lists and return formatted result - diff, etc."""

    name = None

    def format(self, old, old_date, new, new_date):
        raise NotImplementedError()


class ContextDiff(AbstractComparator):
    name = "context_diff"

    def format(self, old, old_date, new, new_date):
        return difflib.context_diff(
            old, new,
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n')


class UnifiedDiff(AbstractComparator):
    name = "unified_diff"

    def format(self, old, old_date, new, new_date):
        return difflib.unified_diff(
            old, new,
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n')


class NDiff(AbstractComparator):
    name = "ndiff"

    def format(self, old, _old_date, new, _new_date):
        return difflib.ndiff(old, new)


def _substract_lists(list1, list2):
    """ Get only items from list1 that not exists in list2"""
    l2set = set(list2)
    return (item for item in list1 if item not in l2set)


class Added(AbstractComparator):
    name = "added"

    def format(self, old, _old_date, new, _new_date):
        """ Get only added items """
        return _substract_lists(new, old)


class Deleted(AbstractComparator):
    name = "deleted"

    def format(self, old, _old_date, new, _new_date):
        """ Get only deleted items """
        return _substract_lists(old, new)


class Modified(AbstractComparator):
    name = "modified"

    def format(self, old, _old_date, new, _new_date):
        """ Make diff and return only modified lines. """
        def _mkdiff():
            diff = difflib.SequenceMatcher(a=old, b=new)
            for change, _, _, begin2, end2 in diff.get_opcodes():
                if change == 'replace':
                    for itm in new[begin2:end2]:
                        yield itm

        return _mkdiff()


class Last(AbstractComparator):
    name = "last"

    def format(self, _prev, _old_date, new, _new_date):
        """ Return last (new) version """
        return new


def get_comparator(name):
    cmpcls = common.find_subclass(AbstractComparator, name)
    if cmpcls:
        return cmpcls()
    raise common.ParamError("Unknown comparator: %s" % name)
