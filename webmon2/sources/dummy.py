#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Dummy source; generate random data
"""
import datetime
import logging
import typing as ty
import random

from webmon2 import common, model

from .abstract import AbstractSource


_LOG = logging.getLogger(__file__)


class DymmySource(AbstractSource):
    """Dummy data generator"""

    name = "dummy"
    params = AbstractSource.params + [
    ]

    def load(self, state: model.SourceState) -> \
            ty.Tuple[model.SourceState, ty.List[model.Entry]]:

        if state and state.last_update and \
                state.last_update > datetime.datetime.now() - \
                datetime.timedelta(minutes=5):
            return state.new_not_modified(), []

        entries = []  # type: ty.List[model.Entry]
        for idx in range(1, random.randrange(2, 10)):
            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now()
            entry.status = 'new'
            entry.title = self._source.name
            entry.url = "dummy"
            entry.content = "dummy entry {} on {}".format(
                idx, datetime.datetime.now()
            )
        new_state = state.new_ok()
        new_state.status = 'updated' if state.last_update else 'new'
        new_state.next_update = datetime.datetime.now() + \
            datetime.timedelta(
                seconds=common.parse_interval(self._source.interval))
        return new_state, entries
