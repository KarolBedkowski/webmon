#!/usr/bin/python3
"""
Comparators - classes that get previous and current version and return
human-readable differences.

Copyright (c) Karol Będkowski, 2016-2017

This file is part of webmon.
Licence: GPLv2+
"""

import difflib
import time
import typing as ty
import hashlib

# import typecheck as tc

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2017"


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
        # pylint: disable=no-self-use,unused-argument,invalid-sequence-index
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
        # pylint: disable=no-self-use,unused-argument,invalid-sequence-index
        raise NotImplementedError()


def _check_changes(ctx: common.Context, changed_lines: int, old_lines: int,
                   changes_th: ty.Optional[float],
                   min_changed: ty.Optional[float]) -> bool:
    if not changed_lines:
        return False

    if changes_th and old_lines:
        changes = float(changed_lines) / old_lines
        ctx.log_debug("changes: %d / %d (%f %%)", changed_lines, old_lines,
                      changes)
        if changes < changes_th:
            ctx.log_info("changes not above threshold (%f<%f)", changes,
                         changes_th)
            return False

    if min_changed and old_lines:
        ctx.log_debug("changes: %f", changed_lines)
        if changed_lines < min_changed:
            ctx.log_info("changes not above minimum (%d<%d)",
                         changed_lines, min_changed)
            return False

    return True


class ContextDiff(AbstractComparator):
    """ Generate formatted context diff of string lists """
    name = "context_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }  # type: Dict[str, ty.Any]

    # @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        # pylint: disable=invalid-sequence-index
        old_lines = old.split('\n')
        res = list(difflib.context_diff(
            old_lines, new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))

        changed_lines = sum(1 for line in res[2:]
                            if line and line[0] != ' ' and line[0] != '*')
        if not _check_changes(ctx, changed_lines, len(old_lines),
                              self.conf.get("changes_threshold"),
                              self.conf.get("min_changed")):
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
        # pylint: disable=invalid-sequence-index
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        old_lines = old.split('\n')
        res = list(difflib.unified_diff(
            old_lines, new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n'))

        changed_lines = sum(1 for line in res[2:]
                            if line and line[0] != ' ' and line[0] != '@')
        if not _check_changes(ctx, changed_lines, len(old_lines),
                              self.conf.get("changes_threshold"),
                              self.conf.get("min_changed")):
            return False, None, None

        return True, "\n".join(res), self.opts


class NDiff(AbstractComparator):
    """ Generate formatted diff in ndiff compare of two strings lists """
    name = "ndiff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    # @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        # pylint: disable=invalid-sequence-index
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        old_lines = old.split('\n')
        res = list(difflib.ndiff(old_lines, new.split('\n')))

        changed_lines = sum(1 for line in res if line and line[0] != ' ')
        if not _check_changes(ctx, changed_lines, len(old_lines),
                              self.conf.get("changes_threshold"),
                              self.conf.get("min_changed")):
            return False, None, None

        return True, "\n".join(res), self.opts


def _instr_separator(instr1: str, instr2: ty.Optional[str]) -> str:
    """ Get only items from instr1 that not exists in instr2"""
    if common.RECORD_SEPARATOR in instr1:
        return common.RECORD_SEPARATOR
    if instr2 and common.RECORD_SEPARATOR in instr2:
        return common.RECORD_SEPARATOR
    return '\n'


def _substract_lists(instr1: str, instr2: str) -> ty.Tuple[str, int, int, int]:
    """ Get only items from instr1 that not exists in instr2"""
    # pylint: disable=invalid-sequence-index
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


def hash_item(item: str) -> str:
    """Create hash for one item"""
    chsum = hashlib.md5()
    chsum.update(item.encode('utf-8'))
    return chsum.hexdigest()


def hash_strings(inp: ty.List[str]) -> ty.Dict[int, int]:
    """Create dict of hashes for items """
    now = int(time.time())  # type: int
    # calculate hashs for new items
    return {hash_item(item): now for item in inp}


class Added(AbstractComparator):
    """ Generate list of added (new) items """
    name = "added"

    # @tc.typecheck
    def new(self, new: str, new_date: str, ctx: common.Context, meta: dict) \
            -> ty.Tuple[str, dict]:
        """ Process new content """
        # pylint: disable=invalid-sequence-index
        sep = _instr_separator(new, None)
        # calculate hashs for new items
        new_hashes = hash_strings(new.split(sep))
        meta = self.opts.copy()
        meta['hashes'] = new_hashes
        return new, meta

    # @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Get only added items """
        # pylint: disable=invalid-sequence-index,too-many-locals

        meta = self.opts.copy()
        # find common separator
        sep = _instr_separator(new, old)
        # calculate hashs for new items
        # hashes in form {hash: ts}
        comparator_opts = ctx.metadata.get('comparator_opts')
        known_hashes = comparator_opts.get('hashes') if comparator_opts \
            else None

        if not known_hashes:
            # previous hashes not found - calculate
            known_hashes = hash_strings(old.split(sep))
            old_cnt = len(known_hashes)
            ctx.log_debug("known_hashes not found; calculated cnt=%d",
                          old_cnt)
        else:
            old_cnt = len(known_hashes)
            ctx.log_debug("known_hashes cnt=%d", old_cnt)
            # remove old hashes
            check_last_days = self.conf.get('check_last_days') or 365
            known_hashes = _drop_old_hashes(known_hashes, check_last_days)
            ctx.log_debug("known_hashes after old filter cnt=%d",
                          len(known_hashes))

        # filter items
        new_items = []
        now = int(time.time())  # type: int
        for item in new.split(sep):
            item_hash = hash_item(item)
            if item_hash not in known_hashes:
                new_items.append(item)
            known_hashes[item_hash] = now

        meta['hashes'] = known_hashes
        changed = len(new_items)
        ctx.log_debug("new_items cnt=%d; all_hashes=%d", changed,
                      len(known_hashes))

        if not _check_changes(ctx, changed, old_cnt,
                              self.conf.get("changes_threshold"),
                              self.conf.get("min_changed")):
            return False, None, None

        if new_items:
            res = sep.join(new_items)
            return True, res, meta
        return False, None, meta


class Deleted(AbstractComparator):
    """ Generate list of deleted (misssing) items """
    name = "deleted"

    # @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Get only deleted items """
        # pylint: disable=invalid-sequence-index

        res, old_cnt, _, changed = _substract_lists(old, new)

        if not _check_changes(ctx, changed, old_cnt,
                              self.conf.get("changes_threshold"),
                              self.conf.get("min_changed")):
            return False, None, None

        return True, res, self.opts


class Last(AbstractComparator):
    """ Return current version """
    name = "last"

    # @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) \
            -> ty.Tuple[bool, ty.Optional[str], ty.Optional[dict]]:
        """ Return last (new) version """
        # pylint: disable=invalid-sequence-index
        return True, new, self.opts


# @tc.typecheck
def get_comparator(name: str, conf: ty.Optional[dict]) -> \
        ty.Optional[AbstractComparator]:
    """ Get comparator object by name"""
    cmpcls = common.find_subclass(AbstractComparator, name)
    if cmpcls:
        return cmpcls(conf or {})
    raise common.ParamError("Unknown comparator: %s" % name)
