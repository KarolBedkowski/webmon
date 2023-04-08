# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Convert html to text.
"""
import logging
import re
import typing as ty
from urllib.parse import urljoin

import html2text as h2t
from flask_babel import lazy_gettext

from webmon2 import common, model

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"
    short_info = lazy_gettext("Convert html to text")
    long_info = lazy_gettext(
        "Try convert html content do plain text; remove all "
        "formatting, images etc."
    )
    params = [
        common.SettingDef(
            "width", lazy_gettext("Max line width"), default=999999
        ),
    ]  # type: ty.List[common.SettingDef]

    def validate(self) -> None:
        super().validate()
        width = self._conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError(r"invalid width: {width!r}")

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        content = _convert(entry.content, self._conf.get("width", 80))
        if entry.url:
            content = _convert_links(content, entry.url)

        entry.content = content
        entry.set_opt("content-type", "markdown")
        yield entry


def _convert(content: str, bodywidth: int) -> str:
    conv = h2t.HTML2Text(bodywidth=bodywidth)
    conv.protect_links = True
    return conv.handle(content)


_RE_LINKS = re.compile(r'\(<([^\'">\s]+)>\)', re.I)
_LINKS_SCHEMA = {"http", "https", "mailto", "ftp"}


def _convert_links(content: str, page_link: str) -> str:
    """convert relative links to absolute"""

    def convert_links(match: re.Match[str]) -> str:
        link = match.group(1)
        url = urljoin(page_link, link)
        return f"(<{url}>)"

    return _RE_LINKS.sub(convert_links, content)
