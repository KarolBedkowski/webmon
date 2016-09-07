#!/usr/bin/python3
"""
Comparators - classes that get previous and current version and return
human-readable differences.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import difflib
import typing as ty

import typecheck as tc

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"


class AbstractComparator(object):
    """Abstract / base class for all comparators.
    Comparator get two lists and return formatted result - diff, etc."""

    name = None  # type: ty.Optional[str]

    # some information about comparator & result
    opts = {
        common.OPTS_PREFORMATTED: False,
    }  # type: Dict[str, ty.Any]

    def __init__(self, ctx) -> None:
        super(AbstractComparator, self).__init__()
        assert isinstance(ctx, common.Context)
        self.ctx = ctx

    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> str:
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
    }  # type: Dict[str, ty.Any]

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> ty.Iterable[str]:
        yield "\n".join(difflib.context_diff(
            old.split('\n'), new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))


class UnifiedDiff(AbstractComparator):
    """ Generate formatted unified diff of string lists """
    name = "unified_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> str:
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        return "\n".join(difflib.unified_diff(
            old.split('\n'), new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))


class NDiff(AbstractComparator):
    """ Generate formatted diff in ndiff compare of two strings lists """
    name = "ndiff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> str:
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        return "\n".join(difflib.ndiff(old.split('\n'), new.split('\n')))


def _substract_lists(instr1: str, instr2: str) -> str:
    """ Get only items from instr1 that not exists in instr2"""
    separator = (
        common.RECORD_SEPARATOR
        if common.RECORD_SEPARATOR in instr1 or
        common.RECORD_SEPARATOR in instr2
        else '\n')

    l2set = set(map(hash, instr2.split(separator)))
    return separator.join(item for item in instr1.split(separator)
                          if hash(item) not in l2set)


class Added(AbstractComparator):
    """ Generate list of added (new) items """
    name = "added"

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> str:
        """ Get only added items """
        return _substract_lists(new, old)


class Deleted(AbstractComparator):
    """ Generate list of deleted (misssing) items """
    name = "deleted"

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> str:
        """ Get only deleted items """
        return _substract_lists(old, new)


class Last(AbstractComparator):
    """ Return current version """
    name = "last"

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str,
                new_date: str) -> str:
        """ Return last (new) version """
        return new


@tc.typecheck
def get_comparator(name: str,
                   ctx: common.Context) -> ty.Optional[AbstractComparator]:
    """ Get comparator object by name"""
    cmpcls = common.find_subclass(AbstractComparator, name)
    if cmpcls:
        return cmpcls(ctx)
    raise common.ParamError("Unknown comparator: %s" % name)
