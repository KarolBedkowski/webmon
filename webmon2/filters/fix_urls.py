#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Convert html to text.
"""
import logging
import typing as ty
from urllib.parse import urljoin

import lxml
import lxml.html
from flask_babel import lazy_gettext

from webmon2 import model

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


class Html2Text(AbstractFilter):
    """Convert relative urls in html content."""

    name = "fix_urls"
    short_info = lazy_gettext("Convert relative URLs")
    long_info = lazy_gettext(
        "Convert relative URLs to absolute when it possible in HTML results."
    )

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.url or not entry.content:
            yield entry
            return

        base = entry.url

        try:
            document = lxml.html.fragment_fromstring(entry.content)
        except lxml.etree.ParserError as err:
            _LOG.warning("parse error: %s", err)
            yield entry
            return

        for node in document.xpath("//img"):
            src = node.attrib.get("src")
            node.attrib["src"] = _convert_link(src, base)

        for node in document.xpath("//a"):
            src = node.attrib.get("href")
            node.attrib["href"] = _convert_link(src, base)

        for node in document.xpath("//source"):
            src = node.attrib.get("srcset")
            node.attrib["srcset"] = " ".join(_convert_srcset_links(src, base))

        entry.content = lxml.etree.tostring(document).decode("utf-8")
        yield entry


def _convert_link(url: str, base: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url

    return urljoin(base, url)


def _convert_srcset_links(srcset: str, base: str) -> ty.Iterable[str]:
    """Create proxied links from srcset.

    srcset is in form srcset="<url>" or
    srcset="<url> <size>, <url> <size>, ..."
    """
    parts = srcset.split(" ")
    if len(parts) == 1:
        yield _convert_link(parts[0], base)
        return

    for idx, part in enumerate(parts):
        if idx % 2:
            # size part
            yield part
        else:
            yield _convert_link(part, base)
