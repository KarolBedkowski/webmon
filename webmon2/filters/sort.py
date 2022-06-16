#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Select entries by matching text.
"""
import typing as ty

from flask_babel import lazy_gettext

from webmon2 import model

from ._abstract import AbstractFilter

_ = ty


class Sort(AbstractFilter):
    """Sort entries"""

    name = "sort"
    short_info = lazy_gettext("Sort elements")
    long_info = lazy_gettext("Sort elements by title and content")

    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,
        curr_state: model.SourceState,
    ) -> model.Entries:
        return sorted(entries, key=lambda e: (e.title, e.content))

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
