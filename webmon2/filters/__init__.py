#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filters
"""
import logging

from webmon2 import common, model

from ._abstract import AbstractFilter


_LOG = logging.getLogger(__file__)
__all__ = (
    "UnknownFilterException",
    "get_filter",
    "filter_by",
    "filters_name",
    "filters_info",
)


def _load_filters():
    from . import html2text
    from . import strip
    from . import diff
    from . import grep
    from . import history
    from . import join
    from . import sort
    from . import wrap
    from . import split_re
    try:
        from . import split_text
    except ImportError as err:
        _LOG.warning("module not found: %s", err)


_load_filters()


class UnknownFilterException(Exception):
    pass


def get_filter(conf) -> AbstractFilter:
    """ Get filter object by configuration """
    name = conf.get("name")
    if not name:
        _LOG.error("missing filter name: %r", conf)
        return None

    rcls = common.find_subclass(AbstractFilter, name)
    _LOG.debug("found filter %r for %s", rcls, name)
    if rcls:
        fltr = rcls(conf)
        return fltr

    raise UnknownFilterException()


def filter_by(filters_conf: [dict], entries: model.Entries,
              prev_state: model.SourceState,
              curr_state: model.SourceState,
              db) \
              -> (model.Entries, model.SourceState):
    """ Apply filters by configuration to entries list. """

    for filter_conf in filters_conf:
        fltr = get_filter(filter_conf)
        fltr.db = db
        fltr.validate()
        entries = fltr.filter(entries, prev_state, curr_state)

    return entries


def filters_name():
    return [name
            for name, scls in common.get_subclasses_with_name(AbstractFilter)]

def filters_info():
    return [(name, scls.short_info, scls.long_info)
            for name, scls in common.get_subclasses_with_name(AbstractFilter)]
