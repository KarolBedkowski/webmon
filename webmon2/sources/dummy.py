#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Dummy source; generate random data
"""
import datetime
import logging
import random
import typing as ty

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)


class DymmySource(AbstractSource):
    """Dummy data generator"""

    name = "dummy"
    params = AbstractSource.params + []
    short_info = "Dummy source for development"
    long_info = ""

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:

        last_check = state.get_state("last_check")

        if (
            last_check
            and last_check > datetime.datetime.now().timestamp() - 120
        ):
            return state.new_not_modified(), []

        entries = []  # type: ty.List[model.Entry]
        for idx in range(random.randrange(2, 10)):
            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now()
            entry.status = model.EntryStatus.NEW
            entry.title = self._source.name
            entry.url = "dummy"
            entry.content = f"dummy entry {idx} on {datetime.datetime.now()}"
            entries.append(entry)

        new_state = state.new_ok()
        new_state.next_update = datetime.datetime.now() + datetime.timedelta(
            seconds=common.parse_interval(self._source.interval)
        )
        new_state.set_state("last_check", datetime.datetime.now().timestamp())
        return new_state, entries

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        return {
            "text": source.name,
            "title": source.name,
            "type": cls.name,
            "xmlUrl": "dummy://",
            "htmlUrl": "dummy://",
        }

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        name = opml_node.get("text") or opml_node["title"]
        if not name:
            raise ValueError("missing text/title")

        return model.Source(kind=cls.name, name=name, settings={})
