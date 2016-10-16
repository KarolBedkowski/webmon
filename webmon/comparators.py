#!/usr/bin/python3
"""
Comparators - classes that get previous and current version and return
human-readable differences.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import difflib
import time
import typing as ty

#import typecheck as tc

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

    def __init__(self, conf: ty.Optional[dict]) -> None:
        super().__init__()
        self.conf = conf

    def new(self, new: str, new_date: str, ctx: common.Context, meta: dict) \
            -> ty.Tuple[str, dict]:
        """ Process new content """
        return new, {}

    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Compare `old` and `new` lists and return formatted result.

        Arguments:
        old -- previous value [list of string]
        old_date -- previous value date [string]
        new -- new value [list of string]
        new_date -- new value date [string]
        ctx -- context [common.Context]
        meta: new metadata [dict]

        Return:
            bool - result - True = ok, False = not changed
            iter<strings>
            dict - options
        """
        raise NotImplementedError()


class ContextDiff(AbstractComparator):
    """ Generate formatted context diff of string lists """
    name = "context_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }  # type: Dict[str, ty.Any]

    #@tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        old_lines = old.split('\n')
        res = list(difflib.context_diff(
            old_lines, new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))
        min_changes = self.conf.get("changes_threshold")
        if min_changes and old_lines and len(res) > 2:
            changed_lines = sum(1 for line in res[2:]
                                if line and line[0] != ' ' and line[0] != '*')
            changes = float(changed_lines) / len(old_date)
            if changes < min_changes:
                ctx.log_info("changes not above threshold (%f<%f)", changes,
                             min_changes)
            return False, None, None
        return True, "\n".join(res), self.opts


class UnifiedDiff(AbstractComparator):
    """ Generate formatted unified diff of string lists """
    name = "unified_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        old_lines = old.split('\n')
        res = list(difflib.unified_diff(
            old_lines, new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))

        min_changes = self.conf.get("changes_threshold")
        if min_changes and old_lines and len(res) > 2:
            changed_lines = sum(1 for line in res[2:]
                                if line and line[0] != ' ' and line[0] != '@')
            changes = float(changed_lines) / len(old_date)
            if changes < min_changes:
                ctx.log_info("changes not above threshold (%f<%f)", changes,
                             min_changes)
            return False, None, None
        return True, "\n".join(res), self.opts


class NDiff(AbstractComparator):
    """ Generate formatted diff in ndiff compare of two strings lists """
    name = "ndiff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    #@tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        old_lines = old.split('\n')
        res = list(difflib.ndiff(old_lines, new.split('\n')))

        min_changes = self.conf.get("changes_threshold")
        if min_changes and old_lines and res:
            changed_lines = sum(1 for line in res if line and line[0] != ' ')
            changes = float(changed_lines) / len(old_date)
            if changes < min_changes:
                ctx.log_info("changes not above threshold (%f<%f)", changes,
                             min_changes)
            return False, None, None
        return True, "\n".join(res), self.opts


def _instr_separator(instr1: str, instr2: ty.Optional[str]) -> str:
    """ Get only items from instr1 that not exists in instr2"""
    if common.RECORD_SEPARATOR in instr1:
        return common.RECORD_SEPARATOR
    if instr2 and common.RECORD_SEPARATOR in instr2:
        return common.RECORD_SEPARATOR
    return '\n'


def _substract_lists(instr1: str, instr2: str) -> str:
    """ Get only items from instr1 that not exists in instr2"""
    separator = _instr_separator(instr1, instr2)

    l2set = set(map(hash, instr2.split(separator)))
    l1itms = instr1.split(separator)
    res = list(item for item in l1itms if hash(item) not in l2set)
    return separator.join(res), len(l1itms), len(l2set), len(res)


def _drop_old_hashes(previous_hash: ty.Dict[str, int], days: int) -> \
        ty.Dict[str, int]:
    if not previous_hash:
        return {}
    limit = time.time() - days * 24 * 60 * 60
    return {hash_: timestamp
            for hash_, timestamp in previous_hash.items()
            if timestamp >= limit}


def hash_strings(inp: str) -> ty.Dict[str, int]:
    now = int(time.time())
    # calculate hashs for new items
    return {hash(item): now for item in inp}


class Added(AbstractComparator):
    """ Generate list of added (new) items """
    name = "added"

    #@tc.typecheck
    def new(self, new: str, new_date: str, ctx: common.Context, meta: dict) \
            -> ty.Tuple[str, dict]:
        """ Process new content """
        check_last_days = self.conf.get('check_last_days')
        if check_last_days:
            sep = _instr_separator(new, None)
            # calculate hashs for new items
            new_hashes = hash_strings(new.split(sep))
            meta = self.opts.copy()
            meta['hashes'] = new_hashes
            return new, meta

        return new, {}

    #@tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Get only added items """
        res, old_cnt, _, changed = _substract_lists(new, old)

        min_changes = self.conf.get("changes_threshold")
        if min_changes and old_cnt:
            changes = float(changed) / old_cnt
            if changes < min_changes:
                ctx.log_info("changes not above threshold (%f<%f)", changes,
                             min_changes)
            return False, None, None

        min_changes = self.conf.get("min_changed")
        if min_changes and old_cnt:
            if changed < min_changes:
                ctx.log_info("changes not above minum (%f<%f)", changed,
                             min_changes)
            return False, None, None

        return True, res, self.opts


class Deleted(AbstractComparator):
    """ Generate list of deleted (misssing) items """
    name = "deleted"

    #@tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Get only deleted items """

        res, old_cnt, _, changed = _substract_lists(old, new)

        min_changes = self.conf.get("changes_threshold")
        if min_changes and old_cnt:
            changes = float(changed) / old_cnt
            if changes < min_changes:
                ctx.log_info("changes not above threshold (%f<%f)", changes,
                             min_changes)
            return False, None, None

        min_changes = self.conf.get("min_changed")
        if min_changes and old_cnt:
            if changed < min_changes:
                ctx.log_info("changes not above minum (%f<%f)", changed,
                             min_changes)
            return False, None, None

        return True, res, self.opts


class Last(AbstractComparator):
    """ Return current version """
    name = "last"

    #@tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Return last (new) version """
        return True, new, self.opts


#@tc.typecheck
def get_comparator(name: str, conf: ty.Optional[dict]) -> \
        ty.Optional[AbstractComparator]:
    """ Get comparator object by name"""
    cmpcls = common.find_subclass(AbstractComparator, name)
    if cmpcls:
        return cmpcls(conf or {})
    raise common.ParamError("Unknown comparator: %s" % name)
