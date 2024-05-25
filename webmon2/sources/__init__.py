# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Data sources
"""

from __future__ import annotations

import typing as ty

import structlog

from webmon2 import common, model

from .abstract import AbstractSource

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)
__all__ = (
    "AbstractSource",
    "UnknownInputError",
    "get_source",
    "sources_info",
    "sources_name",
)


def _load_plugins() -> None:
    # pylint: disable=unused-import,import-outside-toplevel

    from . import dummy, file_input, jamendo, web  # noqa:F401

    try:
        from . import github  # noqa:F401
    except ImportError:
        _LOG.warning("sources: github3 module not found")

    try:
        from . import rss  # noqa:F401
    except ImportError:
        _LOG.warning("sources: feedparser module not found")

    try:
        from . import gitlab  # noqa:F401
    except ImportError:
        _LOG.warning("sources: gitlab module not found")


_load_plugins()


class UnknownInputError(Exception):
    pass


def get_source(
    source: model.Source, sys_settings: model.ConfDict
) -> AbstractSource:
    """Get input class according to configuration"""
    if scls := common.find_subclass(AbstractSource, source.kind):
        return scls(source, sys_settings)  # type: ignore

    raise UnknownInputError


def get_source_class(kind: str) -> ty.Type[AbstractSource] | None:
    return common.find_subclass(AbstractSource, kind)


def sources_name() -> list[str]:
    return [
        name for name, scls in common.get_subclasses_with_name(AbstractSource)
    ]


def sources_info() -> list[tuple[str, str, str]]:
    return [
        (name, scls.short_info, scls.long_info)
        for name, scls in common.get_subclasses_with_name(AbstractSource)
    ]
