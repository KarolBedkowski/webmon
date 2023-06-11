# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Dummy source; generate random data
"""
from __future__ import annotations

import datetime
import logging
import random
import typing as ty

from flask_babel import gettext, lazy_gettext

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)


class DymmySource(AbstractSource):
    """Dummy data generator"""

    name = "dummy"
    params = AbstractSource.params + []
    short_info = lazy_gettext("Dummy source for development")
    long_info = ""

    def load(
        self, state: model.SourceState
    ) -> tuple[model.SourceState, model.Entries]:
        try:
            last_check = int(state.get_prop("last_check"))
        except ValueError:
            last_check = 1

        if (
            last_check
            and last_check
            > datetime.datetime.now(datetime.UTC).timestamp() - 120
        ):
            return state.new_not_modified(), []

        entries = []  # type: list[model.Entry]
        for idx in range(random.randrange(2, 10)):
            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now(
                datetime.UTC
            )
            entry.status = model.EntryStatus.NEW
            entry.title = (
                self._source.name + " " + str(entry.updated) + " " + str(idx)
            )
            entry.url = "dummy"
            entry.content = gettext(
                "dummy entry %(idx)s on %(date)s",
                idx=idx,
                date=datetime.datetime.now(),
            )
            entries.append(entry)

        new_state = state.new_ok()
        assert self._source.interval is not None
        new_state.next_update = datetime.datetime.now(
            datetime.UTC
        ) + datetime.timedelta(
            seconds=common.parse_interval(self._source.interval)
        )
        new_state.set_prop(
            "last_check",
            datetime.datetime.now(datetime.UTC).timestamp(),
        )
        return new_state, entries

    @classmethod
    def to_opml(cls, source: model.Source) -> dict[str, ty.Any]:
        return {
            "text": source.name,
            "title": source.name,
            "type": cls.name,
            "xmlUrl": "dummy://",
            "htmlUrl": "dummy://",
        }

    @classmethod
    def from_opml(cls, opml_node: dict[str, ty.Any]) -> model.Source | None:
        name = opml_node.get("text") or opml_node["title"]
        if not name:
            raise ValueError("missing text/title")

        return model.Source(kind=cls.name, name=name, user_id=0, group_id=0)
