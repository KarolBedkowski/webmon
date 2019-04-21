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

from webmon import model, common

from .abstract import AbstractInput

_LOG = logging.getLogger(__name__)


def _load_plugins():
    from . import file_input
    from . import web_input

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


def get_input(source: model.Source):
    """ Get input class according to configuration """
    scls = common.find_subclass(AbstractInput, source.kind)
    if scls:
        inp = scls(source)
        inp.validate()
        return inp

    raise UnknownInputException()
