#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
"""

import itertools
import typing as ty

from webmon2 import model, common
from ._abstract import AbstractFilter

_ = ty


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    params = [
        common.SettingDef("chars", "Characters to strip"),
    ]  # type: ty.List[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        entry.content = entry.content.strip(self._conf['chars'])
        yield entry


class Compact(AbstractFilter):
    """Remove empty multiple lines characters from input"""

    name = "compact"

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
    params = [
        common.SettingDef("count", "Maximum number of last lines to get",
                          default=20),
    ]  # type: ty.List[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        entry.content = '\n'.join(
            itertools.islice(entry.content.split('\n'), self._conf['count']))
        yield entry
