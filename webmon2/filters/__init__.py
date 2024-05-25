# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.
"""
Filters
"""

from __future__ import annotations

import typing as ty

import structlog

from webmon2 import common, database, model

from ._abstract import AbstractFilter

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)
__all__ = (
    "UnknownFilterError",
    "get_filter",
    "filter_by",
    "filters_name",
    "filters_info",
    "AbstractFilter",
)


def _load_filters() -> None:
    # pylint: disable=unused-import,import-outside-toplevel
    from . import (
        diff,  # noqa:F401
        fix_urls,  # noqa:F401
        grep,  # noqa:F401
        history,  # noqa:F401
        html2text,  # noqa:F401
        join,  # noqa:F401
        score,  # noqa:F401
        sort,  # noqa:F401
        split_re,  # noqa:F401
        strip,  # noqa:F401
        wrap,  # noqa:F401
    )

    try:
        from . import split_text  # noqa:F401
    except ImportError as err:
        _LOG.warning("filters: module split_text not found", error=err)


_load_filters()


class UnknownFilterError(Exception):
    pass


def get_filter(conf: dict[str, ty.Any]) -> AbstractFilter | None:
    """Get filter object by configuration"""
    name = conf.get("name")
    if not name:
        _LOG.error("filters: get filter error; missing name in conf: %r", conf)
        return None

    if rcls := common.find_subclass(AbstractFilter, name):
        _LOG.debug("filters: get filter: found %r for %s", rcls, name)
        fltr: AbstractFilter = rcls(conf)
        return fltr

    _LOG.warning("filters: get filter error: %r not found", name)
    raise UnknownFilterError


def filter_by(
    filters_conf: list[dict[str, ty.Any]],
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


def filters_name() -> list[str]:
    return [
        name for name, scls in common.get_subclasses_with_name(AbstractFilter)
    ]


def filters_info() -> list[tuple[str, str, str]]:
    return [
        (name, scls.short_info, scls.long_info)
        for name, scls in common.get_subclasses_with_name(AbstractFilter)
    ]
