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

from webmon2 import database, model

from ._abstract import AbstractFilter

_ = ty


class History(AbstractFilter):
    """Remove historical visited entries"""

    name = "remove_visited"
    short_info = "Remove element old elements"
    long_info = "Remove elements already loaded in past by given source"

    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,
        curr_state: model.SourceState,
    ) -> model.Entries:
        assert self.db

        entries = list(entries)
        if not entries:
            return

        oids = [entry.calculate_oid() for entry in entries]
        new_oids = set()  # type: ty.Set[str]
        new_oids = database.entries.check_oids(
            self.db, oids, curr_state.source_id
        )
        for entry in entries:
            if entry.oid in new_oids:
                yield entry

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
