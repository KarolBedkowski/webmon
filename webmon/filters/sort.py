#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Select entries by matching text.
"""
import typing as ty
import re

from webmon import model

from ._abstract import AbstractFilter

_ = ty


class Sort(AbstractFilter):
    """Sort entries"""

    name = "sort"
    params = [
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any]]

    def __init__(self, conf):
        super().__init__(conf)

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        entries = list(entries)
        entries.sort(key=lambda e: (e.title, e.content))
        return entries

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
