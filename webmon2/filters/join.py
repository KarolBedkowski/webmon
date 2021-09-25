#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
"""

import typing as ty
from functools import reduce

from webmon2 import model

from ._abstract import AbstractFilter

_ = ty


class Join(AbstractFilter):
    """Join all entries into one conten"""

    name = "join"
    short_info = "Join elements"
    long_info = (
        "Join content from all elements loaded by source to one " "element"
    )

    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,
        curr_state: model.SourceState,
    ) -> model.Entries:
        try:
            first_entry = next(entries)
        except StopIteration:
            return
        for entry in entries:
            first_entry.content = first_entry.content + "\n\n" + entry.content
            first_entry.status = "new"
        yield first_entry

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
