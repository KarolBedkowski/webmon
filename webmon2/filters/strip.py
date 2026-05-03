# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filters that remove white spaces, empty lines etc
"""

from flask_babel import lazy_gettext

from webmon2 import common, model

from ._abstract import AbstractFilter


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    short_info = lazy_gettext("Strip white characters")
    long_info = lazy_gettext(
        "Trim whitespaces from beginning and end of content"
    )

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            entry.content = entry.content.strip()

        yield entry


class Compact(AbstractFilter):
    """Remove empty multiple lines characters from input"""

    name = "compact"
    short_info = lazy_gettext("Remove duplicate empty lines")
    long_info = lazy_gettext("Remove duplicate empty lines from content")

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            entry.content = "\n".join(
                filter(None, map(str.rstrip, entry.content.split("\n")))
            )

        yield entry


class Head(AbstractFilter):
    """Get given top lines from input"""

    name = "head"
    short_info = lazy_gettext("Extract the first lines")
    long_info = lazy_gettext(
        "Extract a specified number of top lines from content")
    params = (
        common.SettingDef(
            "count",
            lazy_gettext("Maximum number of lines"),
            default=20,
        ),
    )

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            cnt = self._conf["count"]
            entry.content = "\n".join(entry.content.split("\n", cnt + 1)[:cnt])

        yield entry
