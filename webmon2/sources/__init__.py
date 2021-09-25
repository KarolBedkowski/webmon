#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Data sources
"""

import logging
import typing as ty

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
__all__ = (
    "UnknownInputException",
    "get_source",
    "sources_name",
    "sources_info",
)


def _load_plugins():
    # pylint: disable=unused-import,import-outside-toplevel

    from . import dummy, file_input, jamendo, web

    try:
        from . import github
    except ImportError:
        _LOG.warning("github3 module not found")

    try:
        from . import rss
    except ImportError:
        _LOG.warning("feedparser module not found")

    try:
        from . import gitlab
    except ImportError:
        _LOG.warning("gitlab module not found")


_load_plugins()


class UnknownInputException(Exception):
    pass


def get_source(source: model.Source, sys_settings):
    """Get input class according to configuration"""
    scls = common.find_subclass(AbstractSource, source.kind)
    if scls:
        src = scls(source, sys_settings)
        return src

    raise UnknownInputException()


def get_source_class(kind: str) -> ty.Optional[AbstractSource]:
    scls = common.find_subclass(AbstractSource, kind)
    return scls


def sources_name():
    return [
        name for name, scls in common.get_subclasses_with_name(AbstractSource)
    ]


def sources_info():
    return [
        (name, scls.short_info, scls.long_info)
        for name, scls in common.get_subclasses_with_name(AbstractSource)
    ]
