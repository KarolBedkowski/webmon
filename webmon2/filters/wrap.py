# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Wrap entry content lines
"""
import textwrap
import typing as ty

from flask_babel import lazy_gettext

from webmon2 import common, model

from ._abstract import AbstractFilter

_ = ty


class Wrap(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "wrap"
    short_info = lazy_gettext("Wrap long lines")
    long_info = lazy_gettext(
        "Wrap long content lines to given width; also allow limit "
        "total number of lines"
    )
    params = [
        common.SettingDef("width", lazy_gettext("Max line width"), default=76),
        common.SettingDef(
            "max_lines", lazy_gettext("Max number of lines"), value_type=int
        ),
    ]  # type: list[common.SettingDef]

    def validate(self) -> None:
        super().validate()
        width = self._conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError(f"invalid width: {width!r}")

        max_lines = self._conf.get("max_lines")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError(f"invalid max_lines: {max_lines!r}")

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            indent = common.get_whitespace_prefix(entry.content)
            entry.content = textwrap.fill(
                entry.content,
                break_long_words=False,
                break_on_hyphens=False,
                initial_indent=indent,
                subsequent_indent=indent,
                max_lines=self._conf["max_lines"],
                width=self._conf["width"],
            )

        yield entry
