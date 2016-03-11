#!/usr/bin/python3
"""
Default filters definition.
"""
import subprocess
import logging
import re

from . import common

_LOG = logging.getLogger(__name__)


class AbstractFilter(object):
    """Base class for all filters.

    Mode:
        * parts - sort whole parts
        * lines - sort all lines in each parts
    """

    name = None
    _required_params = None
    _accepted_modes = ("lines", "parts")

    def __init__(self, conf):
        super(AbstractFilter, self).__init__()
        self.conf = conf
        self._mode = conf.get("mode", "parts")

    def validate(self):
        """ Validate filter parameters """
        for key in self._required_params or []:
            if not self.conf.get(key):
                raise common.ParamError("missing %s parameter" % key)
        if self._mode not in self._accepted_modes:
            raise common.ParamError("invalid mode: %s" % self._mode)

    def filter(self, parts):
        if self._mode == "parts":
            for part in parts:
                yield from self._filter_part(part)

        elif self._mode == "lines":
            for part in parts:
                yield "\n".join("".join(self._filter_part(line)) for line
                                in part.split("\n"))

    def _filter_part(self, text):
        raise NotImplementedError()


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"

    def validate(self):
        super(Html2Text, self).validate()
        width = self.conf.get("width", 9999999)
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid width: %r" % width)

    def _filter_part(self, text):
        assert isinstance(text, str)
        import html2text as h2t
        conv = h2t.HTML2Text(bodywidth=self.conf.get("width", 9999999))
        yield conv.handle(text)


class Strip(AbstractFilter):
    """Strip white spaces from input"""

    name = "strip"

    def _filter_part(self, text):
        assert isinstance(text, str)
        lines = (line.strip() for line in text.split("\n"))
        yield '\n'.join(line for line in lines if line)


class Sort(AbstractFilter):
    """ Sort items. """

    name = "sort"

    def filter(self, parts):
        if self._mode == "parts":
            yield from sorted(parts)

        elif self._mode == "lines":
            outp = []
            for part in parts:
                outp.append("\n".join(sorted(part.split("\n"))))
            outp.sort()
            yield from outp


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    _required_params = ("pattern", )
    _accepted_modes = ("lines", "parts")

    def __init__(self, conf):
        super(Grep, self).__init__(conf)
        self._re = re.compile(conf["pattern"])

    def _filter_part(self, text):
        assert isinstance(text, str)
        if self._re.match(text):
            yield text


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
    _accepted_modes = ("parts", )

    def validate(self):
        super(GetElementsByCss, self).validate()
        sel = self.conf.get("sel")
        from cssselect import GenericTranslator, SelectorError
        try:
            self._expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')

    def _filter_part(self, text):
        assert isinstance(text, str), repr(text)
        yield from _get_elements_by_xpath(text, self._expression)


class GetElementsByXpath(AbstractFilter):
    """Extract elements from html/xml by xpath selector"""

    name = "get-elements-by-xpath"
    _required_params = ("xpath", )
    _accepted_modes = ("parts", )

    def _filter_part(self, text):
        assert isinstance(text, str)
        xpath = self.conf.get("xpath")
        yield from _get_elements_by_xpath(text, xpath)


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
    _accepted_modes = ("parts", )

    def _filter_part(self, text):
        assert isinstance(text, str)
        sel = self.conf.get("sel")
        yield from _get_elements_by_id(text, sel)


class CommandFilter(AbstractFilter):
    """Filter through command"""

    name = "command"
    _required_params = ("command", )

    def _filter_part(self, text):
        assert isinstance(text, str)
        #_LOG.debug("CommandFilter %r, %r", self.conf["command"], text)
        subp = subprocess.run(self.conf["command"],
                              input=text.encode('utf-8'),
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              shell=True)

        res = subp.stdout or subp.stderr or b""
        if res:
            yield res.decode("utf-8")


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
