# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Convert html to text.
"""
import logging

import lxml
import lxml.html
from flask_babel import lazy_gettext

from webmon2 import model

from ._abstract import AbstractFilter

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

        try:
            document = lxml.html.fromstring(entry.content, base_url=entry.url)
        except lxml.etree.ParserError as err:
            _LOG.warning("parse error: %s", err)
            yield entry
            return

        document.make_links_absolute(entry.url)

        try:
            entry.content = lxml.etree.tostring(
                document, encoding="UTF-8"
            ).decode("utf-8")
        except lxml.etree.SerialisationError as err:
            _LOG.warning("serialize error: %s", err)

        yield entry
