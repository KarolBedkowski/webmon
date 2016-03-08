#!/usr/bin/python3

import logging

from . import common

_LOG = logging.getLogger(__name__)


class AbstractFilter(object):
    """docstring for AbstractFilter"""
    def __init__(self, conf):
        super(AbstractFilter, self).__init__()
        self.conf = conf

    def filter(self, inp):
        raise NotImplementedError()


class Html2Text(AbstractFilter):
    """docstring for html2text"""

    name = "html2text"

    def filter(self, inp):
        import html2text as h2t
        for sinp in inp:
            conv = h2t.HTML2Text()
            yield conv.handle(sinp)


class Strip(AbstractFilter):
    """docstring for Strip"""

    name = "strip"

    def filter(self, inp):
        for sinp in inp:
            lines = (line.strip() for line in sinp.split("\n"))
            yield '\n'.join(line for line in lines if line)


def _get_elements_by_xpath(data, expression):
    from lxml import etree

    html_parser = etree.HTMLParser(encoding='utf-8', recover=True,
                                   strip_cdata=True)
    document = etree.fromstringlist([data], html_parser)
    for elem in document.xpath(expression):
        if isinstance(elem, etree._Element):
            text = etree.tostring(elem)
        else:
            text = str(elem)
        if text:
            yield text.decode('utf-8')


class GetElementsByCss(AbstractFilter):
    """docstring for GetElementByCss"""

    name = "get-elements-by-css"

    def filter(self, inp):
        from cssselect import GenericTranslator, SelectorError

        sel = self.conf.get("sel")
        if not sel:
            raise common.ParamError("missing 'sel' param")
        try:
            expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')
        for sinp in inp:
            yield from _get_elements_by_xpath(sinp, expression)


class GetElementsByXpath(AbstractFilter):
    """docstring for GetElementByCss"""

    name = "get-elements-by-xpath"

    def filter(self, inp):
        xpath = self.conf.get("xpath")
        if not xpath:
            raise common.ParamError("missing 'xpath' parameter")
        for sinp in inp:
            yield from _get_elements_by_xpath(sinp, xpath)


def _get_elements_by_id(data, sel):
    from lxml import etree
    html_parser = etree.HTMLParser(encoding='utf-8', recover=True,
                                    strip_cdata=True)
    document = etree.fromstringlist([data], html_parser)
    for elem in document.findall(".//*[@id='" + sel + "']"):
        if isinstance(elem, etree._Element):
            text = etree.tostring(elem)
        else:
            text = str(elem)
        if text:
            yield text.decode('utf-8')


class GetElementsById(AbstractFilter):
    """docstring for GetElementByCss"""

    name = "get-elements-by-id"

    def filter(self, inp):
        sel = self.conf.get("sel")
        if not sel:
            raise common.ParamError("missing 'sel' parameter")
        for sinp in inp:
            yield from _get_elements_by_id(sinp, sel)


def get_filter(conf):
    name = conf.get("name")
    for rcls in getattr(AbstractFilter, "__subclasses__")():
        if getattr(rcls, 'name') == name:
            return rcls(conf)
    _LOG.warn("unknown filter: %s", name)
    return None
