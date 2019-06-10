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
import re

from webmon2 import model, common

from ._abstract import AbstractFilter

_ = ty


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    short_info = "Filter elements by regular expression"
    long_info = "Select element matching or not matching to given pattern."
    params = [
        common.SettingDef("pattern", "Regular expression", required=True),
        common.SettingDef("invert", "Accept items not matching",
                          default=False),
    ]  # type: ty.List[common.SettingDef]

    def __init__(self, conf):
        super().__init__(conf)
        pattern = conf.get("pattern")
        if pattern:
            self._re = re.compile(pattern, re.IGNORECASE | re.MULTILINE |
                                  re.DOTALL)
        else:
            self._re = None

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        if self._conf["invert"]:
            return filter(lambda x: not self._re.match(x.content), entries)
        return filter(lambda x: self._re.match(x.content), entries)

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass
