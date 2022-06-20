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
import typing as ty

from webmon2 import common, database, model

from ._abstract import AbstractFilter

_LOG = logging.getLogger(__name__)
__all__ = (
    "UnknownFilterException",
    "get_filter",
    "filter_by",
    "filters_name",
    "filters_info",
    "AbstractFilter",
)


def _load_filters() -> None:
    # pylint: disable=unused-import,import-outside-toplevel
    from . import (
        diff,
        fix_urls,
        grep,
        history,
        html2text,
        join,
        score,
        sort,
        split_re,
        strip,
        wrap,
    )

    try:
        from . import split_text
    except ImportError as err:
        _LOG.warning("module not found: %s", err)


_load_filters()


class UnknownFilterException(Exception):
    pass


def get_filter(conf: ty.Dict[str, ty.Any]) -> ty.Optional[AbstractFilter]:
    """Get filter object by configuration"""
    name = conf.get("name")
    if not name:
        _LOG.error("missing filter name: %r", conf)
        return None

    rcls = common.find_subclass(AbstractFilter, name)
    _LOG.debug("found filter %r for %s", rcls, name)
    if rcls:
        fltr: AbstractFilter = rcls(conf)
        return fltr

    raise UnknownFilterException()


def filter_by(
    filters_conf: ty.List[ty.Dict[str, ty.Any]],
    entries: model.Entries,
    prev_state: model.SourceState,
    curr_state: model.SourceState,
    db: database.DB,
) -> model.Entries:
    """Apply filters by configuration to entries list."""

    for filter_conf in filters_conf:
        fltr = get_filter(filter_conf)
        if fltr:
            fltr.db = db
            fltr.validate()
            entries = fltr.filter(entries, prev_state, curr_state)

    return entries


def filters_name() -> ty.List[str]:
    return [
        name for name, scls in common.get_subclasses_with_name(AbstractFilter)
    ]


def filters_info() -> ty.List[ty.Tuple[str, str, str]]:
    return [
        (name, scls.short_info, scls.long_info)
        for name, scls in common.get_subclasses_with_name(AbstractFilter)
    ]
