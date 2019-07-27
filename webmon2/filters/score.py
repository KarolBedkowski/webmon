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
import logging

from webmon2 import model, common

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


class Score(AbstractFilter):
    """Apply score to elements by regexp"""

    name = "score"
    short_info = "Change score of elements by defined regular expression"
    long_info = "Change element score according to matched patterns."
    params = [
        common.SettingDef("patterns", "Regular expressions separated by ';'",
                          required=True),
        common.SettingDef("score_change", "Value added do score when match",
                          default=5, value_type=int),
        common.SettingDef("match_many",
                          "Change score on match every pattern",
                          default=True)
    ]  # type: ty.List[common.SettingDef]

    def __init__(self, conf):
        super().__init__(conf)
        patterns = conf.get("patterns")
        if patterns:
            self._re = [
                re.compile(".*(" + pattern.strip() + ").*",
                           re.IGNORECASE | re.MULTILINE | re.DOTALL)
                for pattern in patterns.split(";")]
            _LOG.debug("patterns count: %s", len(self._re))
        else:
            self._re = []
            _LOG.warning("no patterns!")
        self._match_many = conf.get("match_many")
        self._score = int(conf.get("score_change"))

    def _score_for_content(self, *content) -> int:
        add = 0
        if self._match_many:
            add = sum(self._score
                      for pattern in self._re
                      if any(pattern.match(item)
                             for item in content
                             if item))
        elif any(any(pattern.match(item) for item in content if item)
                 for pattern in self._re):
            add = self._score
        return add

    def _filter(self, entry: model.Entry) -> model.Entries:
        add = self._score_for_content(entry.content, entry.title)
        _LOG.debug("apply score %s for entry %s (%r)", add, entry.title,
                   entry.score)
        entry.score += add
        return [entry]
