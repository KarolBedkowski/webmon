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

from webmon import model
from ._abstract import AbstractFilter

_ = ty


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    params = [
        ("chars", "Characters to strip", None, False, None),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any]]

    def _filter(self, entry: model.Entry) -> model.Entries:
        entry.content = entry.content.strip(self._conf['chars'])
        yield entry


class Compact(AbstractFilter):
    """Strip characters from input"""

    name = "compact"
    params = [
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any]]

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
