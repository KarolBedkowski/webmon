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

    def __init__(self, conf: ty.Optional[dict]) -> None:
        super().__init__()
        self.conf = conf

    def new(self, new: str, new_date: str, ctx: common.Context, meta: dict) \
            -> ty.Tuple[str, dict]:
        """ Process new content """
        return new, {}

    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:
        """ Compare `old` and `new` lists and return formatted result.

        Arguments:
        old -- previous value [list of string]
        old_date -- previous value date [string]
        new -- new value [list of string]
        new_date -- new value date [string]
        ctx -- context [common.Context]
        meta: new metadata [dict]

        Return:
            (strings=content, dict=meta)
        """
        raise NotImplementedError()


class ContextDiff(AbstractComparator):
    """ Generate formatted context diff of string lists """
    name = "context_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }  # type: Dict[str, ty.Any]

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:

        return "\n".join(difflib.context_diff(
            old.split('\n'), new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n')), self.opts


class UnifiedDiff(AbstractComparator):
    """ Generate formatted unified diff of string lists """
    name = "unified_diff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        return "\n".join(difflib.unified_diff(
            old.split('\n'), new.split('\n'),
            fromfiledate=old_date, tofiledate=new_date,
            lineterm='\n')), self.opts


class NDiff(AbstractComparator):
    """ Generate formatted diff in ndiff compare of two strings lists """
    name = "ndiff"
    opts = {
        common.OPTS_PREFORMATTED: True,
    }

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:
        old = old.replace(common.RECORD_SEPARATOR, '\n\n')
        new = new.replace(common.RECORD_SEPARATOR, '\n\n')
        return ("\n".join(difflib.ndiff(old.split('\n'), new.split('\n'))),
                self.opts)


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
    return separator.join(item for item in instr1.split(separator)
                          if hash(item) not in l2set)


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

    @tc.typecheck
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

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:
        """ Get only added items """
        check_last_days = self.conf.get('check_last_days')
        meta = self.opts.copy()
        if check_last_days:
            sep = _instr_separator(new, old)
            # calculate hashs for new items
            new_hashes = hash_strings(new.split(sep))
            ctx.log_debug("new_hashes cnt=%d, %r", len(new_hashes), new_hashes)
            # hashes in form {hash, ts}
            comparator_opts = ctx.metadata.get('comparator_opts')
            previous_hash = comparator_opts.get('hashes') if comparator_opts \
                else None
            # put new hashes in meta
            meta['hashes'] = new_hashes
            if previous_hash:
                # found old hashes; can use it for filtering
                ctx.log_debug("previous_hash cnt=%d, %r", len(previous_hash),
                              previous_hash)
                previous_hash = _drop_old_hashes(previous_hash,
                                                 check_last_days)
                ctx.log_debug("previous_hash after old filter cnt=%d, %r",
                              len(previous_hash), previous_hash)
                result = sep.join(item for item in new.split(sep)
                                  if hash(item) not in previous_hash)
                # put old hashes
                meta['hashes'].update(previous_hash)
                return result, meta

        return _substract_lists(new, old), meta


class Deleted(AbstractComparator):
    """ Generate list of deleted (misssing) items """
    name = "deleted"

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:
        """ Get only deleted items """
        return _substract_lists(old, new), self.opts


class Last(AbstractComparator):
    """ Return current version """
    name = "last"

    @tc.typecheck
    def compare(self, old: str, old_date: str, new: str, new_date: str,
                ctx: common.Context, meta: dict) -> ty.Tuple[str, dict]:
        """ Return last (new) version """
        return new, self.opts


@tc.typecheck
def get_comparator(name: str, conf: ty.Optional[dict]) -> \
        ty.Optional[AbstractComparator]:
    """ Get comparator object by name"""
    cmpcls = common.find_subclass(AbstractComparator, name)
    if cmpcls:
        return cmpcls(conf)
    raise common.ParamError("Unknown comparator: %s" % name)
