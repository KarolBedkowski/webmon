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
    params = [
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        entries = list(entries)
        if len(entries) > 1:
            result = entries[0].clone()
            result.content = '\n\n'.join([entry.content for entry in entries])
            return [result]
        return entries

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
