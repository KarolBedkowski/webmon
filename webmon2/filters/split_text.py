# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filters for splitting input text into many entries

"""

import lxml.html
from cssselect import GenericTranslator, SelectorError
from flask_babel import lazy_gettext
from lxml import etree

from webmon2 import common, model

from ._abstract import AbstractFilter


def _get_elements_by_xpath(
    entry: model.Entry, expression: str
) -> model.Entries:
    if not entry.content:
        return

    document = lxml.html.fromstring(entry.content)
    for elem in document.xpath(expression):
        # pylint: disable=protected-access
        if isinstance(elem, etree._Element):  # noqa:SLF001
            content = etree.tostring(elem).decode("utf-8")
        else:
            content = str(elem)

        yield _new_entry(entry, content)


class GetElementsByCss(AbstractFilter):
    """Extract elements from html/xml by css selector"""

    name = "get-elements-by-css"
    short_info = lazy_gettext("Extract elements using a CSS query")
    long_info = lazy_gettext(
        "Extract elements from the content using specified "
        "CSS query"
    )
    params = (
        common.SettingDef(
            "sel", lazy_gettext("Selector"), required=True, multiline=True
        ),
    )

    def __init__(self, config: model.ConfDict) -> None:
        super().__init__(config)
        self._expression: str = ""

    def validate(self) -> None:
        super().validate()
        sel = self._conf["sel"]
        try:
            self._expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError as err:
            raise ValueError("Invalid CSS selector for filtering") from err

    def _filter(self, entry: model.Entry) -> model.Entries:
        yield from _get_elements_by_xpath(entry, self._expression)


class GetElementsByXpath(AbstractFilter):
    """Extract elements from html/xml by xpath selector"""

    name = "get-elements-by-xpath"
    short_info = lazy_gettext("Extract elements using XPath")
    long_info = lazy_gettext(
        "Extract elements from the HTML/XML content using specified xpath "
        "expression"
    )
    params = (
        common.SettingDef(
            "xpath", lazy_gettext("Selector"), required=True, multiline=True
        ),
    )
    stop_change_content = True

    def _filter(self, entry: model.Entry) -> model.Entries:
        yield from _get_elements_by_xpath(entry, self._conf["xpath"])


class GetElementsById(AbstractFilter):
    """Extract elements from html/xml by element id"""

    name = "get-elements-by-id"
    short_info = lazy_gettext("Extract elements with ID")
    long_info = lazy_gettext(
        "Extract an element with specified ID from the HTML content"
    )
    params = (
        common.SettingDef(
            "sel", lazy_gettext("Selector"), required=True, multiline=True
        ),
    )

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return

        document = lxml.html.fromstring(entry.content)
        for elem in document.xpath(".//*[@id=$id]", id=self._conf["sel"]):
            # pylint: disable=protected-access
            if isinstance(elem, etree._Element):  # noqa: SLF001
                if text := etree.tostring(elem).decode("utf-8"):
                    yield _new_entry(entry, text)

            else:
                yield _new_entry(entry, str(elem))


def _new_entry(entry: model.Entry, content: str) -> model.Entry:
    new_entry = entry.clone()
    new_entry.status = model.EntryStatus.NEW
    new_entry.content = content
    return new_entry
