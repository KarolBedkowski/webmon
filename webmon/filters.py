#!/usr/bin/python3
"""
Default filters definition.
"""

import logging
import re

from . import common

_LOG = logging.getLogger(__name__)


class AbstractFilter(object):
    """Base class for all filters """

    name = None
    _required_params = None

    def __init__(self, conf):
        super(AbstractFilter, self).__init__()
        self.conf = conf

    def validate(self):
        """ Validate filter parameters """
        for key in self._required_params or []:
            if not self.conf.get(key):
                raise common.ParamError("missing %s parameter" % key)

    def filter(self, inp):
        raise NotImplementedError()


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"

    def filter(self, inp):
        import html2text as h2t
        for sinp in inp:
            conv = h2t.HTML2Text(bodywidth=self.conf.get("width", 9999999))
            yield conv.handle(sinp)


class Strip(AbstractFilter):
    """Strip white spaces from input"""

    name = "strip"

    def filter(self, inp):
        for sinp in inp:
            lines = (line.strip() for line in sinp.split("\n"))
            yield '\n'.join(line for line in lines if line)


class Sort(AbstractFilter):
    """ Sort items in one of mode:
        * parts - sort whole parts
        * lines - sort all lines in each parts
        * full - sort parts and lines in it
        * auto - if it is only one part - sort lines; else sort parts (default)
    """

    name = "sort"

    def filter(self, inp):
        mode = self.conf.get("mode", "auto")
        if mode == "auto":
            inp = list(inp)
            mode = "lines" if len(inp) == 1 else "parts"
        if mode == "parts":
            yield from sorted(inp)
            return
        if mode == "lines":
            for sinp in inp:
                yield "\n".join(sorted(sinp.split("\n")))
            return
        if mode == "full":
            for sinp in sorted(inp):
                yield "\n".join(sorted(sinp.split("\n")))
            return
        raise common.ParamError("invalid mode %s" % mode)


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    _required_params = ("pattern", )

    def __init__(self, conf):
        super(Grep, self).__init__(conf)
        self._re = re.compile(conf["pattern"])

    def filter(self, inp):
        mode = self.conf.get("mode", "auto")
        if mode == "auto":
            inp = list(inp)
            mode = "lines" if len(inp) == 1 else "parts"
        if mode == "parts":
            for sinp in inp:
                if self._re.match(sinp):
                    yield sinp
            return
        if mode == "lines":
            for sinp in inp:
                lines = "\n".join(line for line in sinp.split("\n")
                                  if self._re.match(line))
                if lines:
                    yield lines
            return
        raise common.ParamError("invalid mode %s" % mode)


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
    """Extract elements from html/xml by css selector"""

    name = "get-elements-by-css"
    _required_params = ("sel", )

    def filter(self, inp):
        from cssselect import GenericTranslator, SelectorError

        sel = self.conf.get("sel")
        try:
            expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')
        for sinp in inp:
            yield from _get_elements_by_xpath(sinp, expression)


class GetElementsByXpath(AbstractFilter):
    """Extract elements from html/xml by xpath selector"""

    name = "get-elements-by-xpath"
    _required_params = ("xpath", )

    def filter(self, inp):
        xpath = self.conf.get("xpath")
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
    """Extract elements from html/xml by element id """

    name = "get-elements-by-id"
    _required_params = ("sel", )

    def filter(self, inp):
        sel = self.conf.get("sel")
        for sinp in inp:
            yield from _get_elements_by_id(sinp, sel)


def get_filter(conf):
    """ Get filter object by configuration """
    if 'name' not in conf:
        _LOG.warning("missing filter name in: %r", conf)
        return None
    name = conf.get("name")
    for rcls in getattr(AbstractFilter, "__subclasses__")():
        if getattr(rcls, 'name') == name:
            fltr = rcls(conf)
            fltr.validate()
            return fltr
    _LOG.warning("unknown filter: %s", name)
    return None
