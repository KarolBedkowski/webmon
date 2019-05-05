#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Filters for splitting input text into many entries

"""
import io
import typing as ty
import logging

from lxml import etree
from cssselect import GenericTranslator, SelectorError

from webmon2 import model, common

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


def _get_elements_by_xpath(entry: model.Entry, expression: str):
    # pylint: disable=no-member
    html_parser = etree.HTMLParser(encoding='utf-8', recover=True,
                                   strip_cdata=True)
    if not entry.content:
        return
    document = etree.parse(io.StringIO(entry.content), html_parser)
    for elem in document.xpath(expression):
        # pylint: disable=protected-access
        if isinstance(elem, etree._Element):
            content = etree.tostring(elem).decode('utf-8')
        else:
            content = str(elem)
        yield _new_entry(entry, content)


class GetElementsByCss(AbstractFilter):
    """Extract elements from html/xml by css selector"""

    name = "get-elements-by-css"
    short_info = "Extract elements by CSS query"
    long_info = "Search and extract element from content by given CSS query"
    params = [
        common.SettingDef("sel", "selector", required=True),
    ]  # type: ty.List[common.SettingDef]

    def __init__(self, conf):
        super().__init__(conf)
        self._expression = None

    def validate(self):
        super().validate()
        sel = self._conf["sel"]
        try:
            self._expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')

    def _filter(self, entry: model.Entry) -> model.Entries:
        yield from _get_elements_by_xpath(entry, self._expression)


class GetElementsByXpath(AbstractFilter):
    """Extract elements from html/xml by xpath selector"""

    name = "get-elements-by-xpath"
    short_info = "Extract elements by xpath"
    long_info = "Search and extract elements from html/xml content "\
        "by given xpath"
    params = [
        common.SettingDef("xpath", "selector", required=True),
    ]  # type: ty.List[common.SettingDef]
    stop_change_content = True

    def _filter(self, entry: model.Entry) -> model.Entries:
        yield from _get_elements_by_xpath(entry, self._conf["xpath"])


class GetElementsById(AbstractFilter):
    """Extract elements from html/xml by element id """

    name = "get-elements-by-id"
    short_info = "Extract elements by given ID"
    long_info = "Search and extract element from html content by given ID"
    params = [
        common.SettingDef("sel", "selector", required=True),
    ]  # type: ty.List[common.SettingDef]

    def _filter(self, entry: model.Entry) -> model.Entries:
        # pylint: disable=no-member
        html_parser = etree.HTMLParser(encoding='utf-8', recover=True,
                                       strip_cdata=True)
        if not entry.content:
            return
        document = etree.parse(io.StringIO(entry.content), html_parser)
        for elem in document.findall(".//*[@id='" + self._conf["sel"] + "']"):
            # pylint: disable=protected-access
            if isinstance(elem, etree._Element):
                text = etree.tostring(elem).decode('utf-8')
                if text:
                    yield _new_entry(entry, text)
            else:
                yield _new_entry(entry, str(elem))


def _new_entry(entry, content):
    new_entry = entry.clone()
    new_entry.status = 'new'
    new_entry.content = content
    return new_entry
