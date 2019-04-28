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

from webmon2 import model

from ._abstract import AbstractFilter

_ = ty


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    params = [
        ("pattern", "Regular expression", None, True, None, str),
        ("invert", "Accept items not matching", False, False, None, bool),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def __init__(self, conf):
        super().__init__(conf)
        self._re = re.compile(conf["pattern"], re.IGNORECASE | re.MULTILINE |
                              re.DOTALL)

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        if self._conf["invert"]:
            return filter(lambda x: not self._re.match(x.content), entries)
        return filter(lambda x: self._re.match(x.content), entries)

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass