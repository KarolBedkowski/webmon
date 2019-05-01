#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""

"""

import logging

from webmon2 import model, common

from .abstract import AbstractInput

_LOG = logging.getLogger(__name__)
__all__ = (
    "UnknownInputException",
    "get_input",
    "enumerate_inputs"
)


def _load_plugins():
    from . import file_input
    from . import web_input
    from . import jamendo

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


def get_input(source: model.Source, sys_settings):
    """ Get input class according to configuration """
    scls = common.find_subclass(AbstractInput, source.kind)
    if scls:
        inp = scls(source, sys_settings)
        return inp

    raise UnknownInputException()


def enumerate_inputs():
    return [name
            for name, scls in common.get_subclasses_with_name(AbstractInput)]
