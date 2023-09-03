# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Select entries by matching text.
"""
from __future__ import annotations

import re
import typing as ty

from flask_babel import lazy_gettext

from webmon2 import common, model

from ._abstract import AbstractFilter

_ = ty


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    short_info = lazy_gettext("Filter elements by regular expression")
    long_info = lazy_gettext(
        "Select elements matching or not matching to given pattern."
    )
    params = [
        common.SettingDef(
            "pattern",
            lazy_gettext("Regular expression"),
            required=True,
            multiline=True,
        ),
        common.SettingDef(
            "invert", lazy_gettext("Accept items not matching"), default=False
        ),
    ]  # type: list[common.SettingDef]

    def __init__(self, conf: model.ConfDict) -> None:
        super().__init__(conf)
        pattern = conf.get("pattern")
        # self._re: ty.Optional[re.Pattern[str]]  py3.7
        self._re: re.Pattern | None  # type: ignore
        if pattern:
            self._re = re.compile(
                pattern, re.IGNORECASE | re.MULTILINE | re.DOTALL
            )
        else:
            self._re = None

    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,
        curr_state: model.SourceState,
    ) -> model.Entries:
        if not self._re:
            return entries

        rep = self._re

        if self._conf["invert"]:
            return filter(
                lambda x: not x.content or not rep.match(x.content), entries
            )

        return filter(lambda x: x.content and rep.match(x.content), entries)

    def _filter(self, entry: model.Entry) -> model.Entries:
        raise NotImplementedError()
