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


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    params = [
        ("chars", "Characters to strip", None, False, None, str),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def _filter(self, entry: model.Entry) -> model.Entries:
        entry.content = entry.content.strip(self._conf['chars'])
        yield entry


class Compact(AbstractFilter):
    """Strip characters from input"""

    name = "compact"
    params = [
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return

        def clean():
            prev_space = False
            for line in map(str.rstrip, entry.content.split(None)):
                if not line and prev_space:
                    continue
                prev_space = not line
                yield line

        entry.content = '\n'.join(clean())
        yield entry


class Head(AbstractFilter):
    """Get given top lines from input"""

    name = "head"
    params = [
        ("count", "Maximum number of last lines to get", 20, True, None, int),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        entry.content = '\n'.join(
            entry.content.split(None)[:self._conf['count']])
        yield entry