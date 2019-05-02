#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
"""

import typing as ty

from webmon2 import model
from ._abstract import AbstractFilter

_ = ty


class Join(AbstractFilter):
    """Join all entries into one conten"""

    name = "join"

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        try:
            first_entry = next(entries)
        except StopIteration:
            return
        for entry in entries:
            first_entry.content = first_entry.content + "\n\n" + entry.content
        yield first_entry

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
