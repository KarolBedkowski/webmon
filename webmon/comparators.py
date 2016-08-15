#!/usr/bin/python3
"""
Comparators - classes that get previous and current version and return
human-readable differences.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import difflib

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"


class AbstractComparator(object):
    """Abstract / base class for all comparators.
    Comparator get two lists and return formatted result - diff, etc."""

    name = None

    # some information about comparator & result
    opts = {
        common.OPTS_PREFORMATTED: False,
    }

    def __init__(self, ctx):
        super(AbstractComparator, self).__init__()
        assert isinstance(ctx, common.Context)
        self.ctx = ctx

    def compare(self, old, old_date, new, new_date):
        """ Compare `old` and `new` lists and return formatted result.

        Arguments:
        :param old: previous value [list of string]
        :param old_date: previous value date [string]
        :param new: new value [list of string]
        :param new_date: new value date [string]

        Return:
            iter<strings>
        """
        raise NotImplementedError()


class ContextDiff(AbstractComparator):
    """ Generate formatted context diff of string lists """
    name = "context_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    def compare(self, old, old_date, new, new_date):
        yield "\n".join(difflib.context_diff(
            old, new,
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))


class UnifiedDiff(AbstractComparator):
    """ Generate formatted unified diff of string lists """
    name = "unified_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    def compare(self, old, old_date, new, new_date):
        yield "\n".join(difflib.unified_diff(
            old, new,
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))


class NDiff(AbstractComparator):
    """ Generate formatted diff in ndiff compare of two strings lists """
    name = "ndiff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    def compare(self, old, _old_date, new, _new_date):
        yield "\n".join(difflib.ndiff(old, new))


def _substract_lists(list1, list2):
    """ Get only items from list1 that not exists in list2"""
    l2set = set(list2)
    return (item for item in list1 if item not in l2set)


class Added(AbstractComparator):
    """ Generate list of added (new) items """
    name = "added"

    def compare(self, old, _old_date, new, _new_date):
        """ Get only added items """
        return _substract_lists(new, old)


class Deleted(AbstractComparator):
    """ Generate list of deleted (misssing) items """
    name = "deleted"

    def compare(self, old, _old_date, new, _new_date):
        """ Get only deleted items """
        return _substract_lists(old, new)


class Modified(AbstractComparator):
    """ Generate list of modified items """
    name = "modified"

    def compare(self, old, _old_date, new, _new_date):
        """ Make diff and return only modified lines. """
        def _mkdiff():
            diff = difflib.SequenceMatcher(a=old, b=new)
            for change, _, _, begin2, end2 in diff.get_opcodes():
                if change == 'replace':
                    for itm in new[begin2:end2]:
                        yield itm

        return _mkdiff()


class Last(AbstractComparator):
    """ Return current version """
    name = "last"

    def compare(self, _prev, _old_date, new, _new_date):
        """ Return last (new) version """
        return new


def get_comparator(name, ctx):
    """ Get comparator object by name"""
    cmpcls = common.find_subclass(AbstractComparator, name)
    if cmpcls:
        return cmpcls(ctx)
    raise common.ParamError("Unknown comparator: %s" % name)
