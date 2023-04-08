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


class FixHtmlUrls(AbstractFilter):
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
            document = lxml.html.fromstring(entry.content, base_url=entry.url)
        except lxml.etree.ParserError as err:
            _LOG.warning("parse error: %s", err)
            yield entry
            return

        document.make_links_absolute(base)

        # for node in document.xpath("//img"):
        #     if src := node.attrib.get("src"):
        #         node.attrib["src"] = _convert_link(src, base)

        # for node in document.xpath("//a"):
        #     if src := node.attrib.get("href"):
        #         node.attrib["href"] = _convert_link(src, base)

        # for node in document.xpath("//source"):
        #     if src := node.attrib.get("srcset"):
        #         node.attrib["srcset"] = ",".join(
        #             _convert_srcset_links(src, base)
        #         )

        try:
            entry.content = lxml.etree.tostring(
                document, encoding="UTF-8"
            ).decode("utf-8")
        except lxml.etree.SerialisationError as err:
            _LOG.warning("serialize error: %s", err)

        yield entry


def _convert_link(url: str, base: str) -> str:
    if url.startswith(("http://", "https://")):
        return url

    return urljoin(base, url)


def _convert_srcset_links(srcset: str, base: str) -> ty.Iterable[str]:
    """Create proxied links from srcset.

    srcset is in form srcset="<url>" or
    srcset="<url> <size>, <url> <size>, ..."
    """
    for part in srcset.split(","):
        url, sep, size = part.partition(" ")
        url = _convert_link(url, base)
        yield f"{url}{sep}{size}"
