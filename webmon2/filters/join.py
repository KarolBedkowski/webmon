# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filter that join many entries into one.
"""

import typing as ty
from functools import reduce

import structlog
from flask_babel import lazy_gettext

from webmon2 import model

from ._abstract import AbstractFilter

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)

_MAX_TITLE_WIDTH: ty.Final[int] = 80


def _join_entries(
    first_entry: model.Entry, next_entry: model.Entry
) -> model.Entry:
    first_entry.content = (
        (first_entry.content or "") + "\n\n" + (next_entry.content or "")
    )

    if next_entry.title:
        if not first_entry.title:
            title = "… | " + next_entry.title
        elif (
            len(first_entry.title) < _MAX_TITLE_WIDTH
            and first_entry.title != next_entry.title
        ):
            title = first_entry.title + " | " + next_entry.title
        else:
            title = first_entry.title

        if len(title) > _MAX_TITLE_WIDTH:
            title = title[:_MAX_TITLE_WIDTH] + "…"

        first_entry.title = title

    first_entry.status = model.EntryStatus.NEW
    return first_entry


class Join(AbstractFilter):
    """Join all entries into one entry."""

    name = "join"
    short_info = lazy_gettext("Join elements")
    long_info = lazy_gettext(
        "Join content from all elements loaded by source to one element"
    )

    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,  # noqa:ARG002
        curr_state: model.SourceState,  # noqa:ARG002
    ) -> model.Entries:
        try:
            yield reduce(_join_entries, entries)
        except TypeError as err:
            # empty collection
            _LOG.debug("filters: error joining", entries=entries, error=err)

    def _filter(self, entry: model.Entry) -> model.Entries:
        raise NotImplementedError
