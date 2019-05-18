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

from webmon2 import model, common

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
__all__ = (
    "UnknownInputException",
    "get_source",
    "sources_name",
    "sources_info",
)


def _load_plugins():
    from . import file_input
    from . import web
    from . import jamendo
    from . import dummy

    try:
        from . import github
    except ImportError:
        _LOG.warn("github3 module not found")

    try:
        from . import rss
    except ImportError:
        _LOG.warn("feedparser module not found")


_load_plugins()


class UnknownInputException(Exception):
    pass


def get_source(source: model.Source, sys_settings):
    """ Get input class according to configuration """
    scls = common.find_subclass(AbstractSource, source.kind)
    if scls:
        src = scls(source, sys_settings)
        return src

    raise UnknownInputException()


def get_source_class(source: model.Source):
    scls = common.find_subclass(AbstractSource, source.kind)
    return scls


def sources_name():
    return [name
            for name, scls in common.get_subclasses_with_name(AbstractSource)]


def sources_info():
    return [(name, scls.short_info, scls.long_info)
            for name, scls in common.get_subclasses_with_name(AbstractSource)]
