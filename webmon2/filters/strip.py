# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filters that remove white spaces, empty lines etc
"""

import typing as ty

from flask_babel import lazy_gettext

from webmon2 import common, model

from ._abstract import AbstractFilter

_ = ty


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    short_info = lazy_gettext("Remove white characters")
    long_info = lazy_gettext(
        "Remove white characters from beginning and end of content"
    )
    params = []  # type: list[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            entry.content = entry.content.strip()

        yield entry


class Compact(AbstractFilter):
    """Remove empty multiple lines characters from input"""

    name = "compact"
    short_info = lazy_gettext("Remove duplicated empty lines")
    long_info = lazy_gettext("Remove duplicated empty lines from content")

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            entry.content = "\n".join(
                filter(None, map(str.rstrip, entry.content.split("\n")))
            )

        yield entry


class Head(AbstractFilter):
    """Get given top lines from input"""

    name = "head"
    short_info = lazy_gettext("Get only first lines")
    long_info = lazy_gettext("Get defined number top lines from content")
    params = [
        common.SettingDef(
            "count",
            lazy_gettext("Maximum number of lines"),
            default=20,
        ),
    ]  # type: list[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            cnt = self._conf["count"]
            entry.content = "\n".join(entry.content.split("\n", cnt + 1)[:cnt])

        yield entry
