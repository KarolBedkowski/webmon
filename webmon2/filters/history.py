#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filter that remove already visited items.
"""

import typing as ty

from webmon2 import model, database
from ._abstract import AbstractFilter

_ = ty


class History(AbstractFilter):
    """Remove historical visited entries"""

    name = "remove_visited"

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        entries = list(entries)
        if not entries:
            return
        oids = [entry.calculate_oid() for entry in entries]
        visited_oids = set()  # type: ty.Set[str]
        with database.DB.get() as db:
            visited_oids = database.entries.check_oids(
                db, oids, curr_state.source_id)
        yield from (entry for entry in entries
                    if entry.oid not in visited_oids)

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
