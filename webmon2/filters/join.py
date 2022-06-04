#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filter that join many entries into one.
"""

import logging
import typing as ty
from functools import reduce

from webmon2 import model

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


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
            len(first_entry.title) < 80
            and first_entry.title != next_entry.title
        ):
            title = first_entry.title + " | " + next_entry.title
        else:
            title = first_entry.title

        if len(title) > 80:
            title = title[:80] + "…"

        first_entry.title = title

    first_entry.status = model.EntryStatus.NEW
    return first_entry


class Join(AbstractFilter):
    """Join all entries into one conten"""

    name = "join"
    short_info = "Join elements"
    long_info = (
        "Join content from all elements loaded by source to one element"
    )

    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,
        curr_state: model.SourceState,
    ) -> model.Entries:
        try:
            yield reduce(_join_entries, entries)
        except TypeError as err:
            # empty collection
            _LOG.debug("join error: %s", err)

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
