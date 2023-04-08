# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Data sources
"""
from __future__ import annotations

import logging
import typing as ty

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
__all__ = (
    "AbstractSource",
    "UnknownInputException",
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
        _LOG.warning("github3 module not found")

    try:
        from . import rss  # noqa:F401
    except ImportError:
        _LOG.warning("feedparser module not found")

    try:
        from . import gitlab  # noqa:F401
    except ImportError:
        _LOG.warning("gitlab module not found")


_load_plugins()


class UnknownInputException(Exception):
    pass


def get_source(
    source: model.Source, sys_settings: model.ConfDict
) -> AbstractSource:
    """Get input class according to configuration"""
    scls = common.find_subclass(AbstractSource, source.kind)
    if scls:
        src = scls(source, sys_settings)
        return src  # type: ignore

    raise UnknownInputException()


def get_source_class(kind: str) -> ty.Optional[ty.Type[AbstractSource]]:
    scls = common.find_subclass(AbstractSource, kind)
    return scls


def sources_name() -> ty.List[str]:
    return [
        name for name, scls in common.get_subclasses_with_name(AbstractSource)
    ]


def sources_info() -> ty.List[ty.Tuple[str, str, str]]:
    return [
        (name, scls.short_info, scls.long_info)
        for name, scls in common.get_subclasses_with_name(AbstractSource)
    ]
