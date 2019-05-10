#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filters that remove white spaces, empty lines etc
"""

import typing as ty

from webmon2 import model, common
from ._abstract import AbstractFilter

_ = ty


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    short_info = "Remove white characters"
    long_info = "Remove white characters from begging and end of content"
    params = [
    ]  # type: ty.List[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        entry.content = entry.content.strip()
        yield entry


class Compact(AbstractFilter):
    """Remove empty multiple lines characters from input"""

    name = "compact"
    short_info = "Remove duplicated empty lines"
    long_info = "Remove duplicated empty lines from content"

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        entry.content = '\n'.join(filter(
            None, map(str.rstrip, entry.content.split('\n'))))
        if entry.content:
            yield entry


class Head(AbstractFilter):
    """Get given top lines from input"""

    name = "head"
    short_info = "Get only first lines"
    long_info = "Get defined number top lines from content"
    params = [
        common.SettingDef("count", "Maximum number of last lines to get",
                          default=20),
    ]  # type: ty.List[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        cnt = self._conf['count']
        entry.content = '\n'.join(entry.content.split('\n', cnt + 1)[:cnt])
        yield entry
