# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Select entries by matching text.
"""
from __future__ import annotations

import logging
import re
import typing as ty

from flask_babel import lazy_gettext

from webmon2 import common, model

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


class Score(AbstractFilter):
    """Apply score to elements by regexp"""

    name = "score"
    short_info = lazy_gettext(
        "Change score of elements by defined regular expression"
    )
    long_info = lazy_gettext(
        "Change element score according to matched patterns."
    )
    params = [
        common.SettingDef(
            "patterns",
            lazy_gettext("Regular expressions separated by ';'"),
            required=True,
            multiline=True,
        ),
        common.SettingDef(
            "score_change",
            lazy_gettext("Value added do score when match"),
            default=5,
            value_type=int,
        ),
        common.SettingDef(
            "match_many",
            lazy_gettext("Change score on match every pattern"),
            default=True,
        ),
    ]  # type: list[common.SettingDef]

    def __init__(self, conf: model.ConfDict) -> None:
        super().__init__(conf)
        patterns = conf.get("patterns")
        if patterns:
            self._re = [
                re.compile(
                    ".*(" + pattern.strip() + ").*",
                    re.IGNORECASE | re.MULTILINE | re.DOTALL,
                )
                for pattern in patterns.split(";")
            ]
            _LOG.debug("patterns count: %s", len(self._re))
        else:
            self._re = []
            _LOG.warning("no patterns!")

        self._match_many = conf.get("match_many")
        self._score = int(conf.get("score_change", 0))

    def _score_for_content(self, *content: str | None) -> int:
        add = 0
        if self._match_many:
            add = sum(
                self._score
                for pattern in self._re
                if any(pattern.match(item) for item in content if item)
            )
        elif any(
            any(pattern.match(item) for item in content if item)
            for pattern in self._re
        ):
            add = self._score

        return add

    def _filter(self, entry: model.Entry) -> model.Entries:
        try:
            add = self._score_for_content(entry.content, entry.title)
            _LOG.debug(
                "apply score %s for entry %s (%r)",
                add,
                entry.title,
                entry.score,
            )
            entry.score += add
        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("apply score error: %s; entry %s", err, entry)

        return [entry]
