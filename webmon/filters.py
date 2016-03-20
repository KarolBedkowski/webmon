#!/usr/bin/python3
"""
Default filters definition.
Filters get one content and transform it to another.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""
import subprocess
import logging
import re
import textwrap
import csv

try:
    from lxml import etree
except ImportError:
    try:
        import xml.etree.cElementTree as etree
    except ImportError:
        try:
            import xml.etree.ElementTree as etree
        except ImportError:
            etree = None

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

_LOG = logging.getLogger(__name__)


class AbstractFilter(object):
    """Base class for all filters.

    Mode:
        * parts - filter whole parts
        * lines - filter all lines in each parts
    """

    name = None
    # parameters - list of tuples (name, description, default, required)
    params = [
        ("mode", "Filtering mode", "parts", True),
    ]
    _accepted_modes = ("lines", "parts")

    def __init__(self, conf, context):
        super(AbstractFilter, self).__init__()
        self.context = context
        self.conf = {key: val for key, _, val, _ in self.params}
        self.conf.update(conf)
        self._mode = conf.get("mode", "parts")

    def validate(self):
        """ Validate filter parameters """
        for name, _, _, required in self.params or []:
            if required and not self.conf.get(name):
                raise common.ParamError("missing parameter " + name)
        if self._mode not in self._accepted_modes:
            raise common.ParamError("invalid mode: %s" % self._mode)

    def filter(self, parts):
        if self._mode == "parts":
            for part in parts:
                yield from self._filter(part)

        elif self._mode == "lines":
            for part in parts:
                yield from ("\n".join(self._filter(line))
                            for line in part.split("\n"))

    def _filter(self, text):
        """ Filter text and return iter<str> new one or more items"""
        raise NotImplementedError()


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("width", "Max line width", 999999, True),
    ]

    def validate(self):
        super(Html2Text, self).validate()
        width = self.conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid width: %r" % width)

    def _filter(self, text):
        assert isinstance(text, str)
        import html2text as h2t
        conv = h2t.HTML2Text(bodywidth=self.conf.get("width"))
        yield conv.handle(text)


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("chars", "Characters to strip", None, False),
    ]

    def _filter(self, text):
        assert isinstance(text, str)
        yield text.strip(self.conf['chars'])


class Split(AbstractFilter):
    """Split input on given character"""

    name = "split"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("separator", "Delimiter string (default \\n)", None, False),
        ("max_split", "Maximum number of lines", -1, False),
    ]

    def _filter(self, text):
        assert isinstance(text, str)
        sep = self.conf['separator']
        yield from text.split("\n" if sep is None else sep,
                              self.conf['max_split'])


class Sort(AbstractFilter):
    """ Sort items. """

    name = "sort"

    def filter(self, parts):
        if self._mode == "parts":
            yield from sorted(parts)

        elif self._mode == "lines":
            # sort lines in each part
            for part in parts:
                yield "\n".join(sorted(part.split("\n")))


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("pattern", "Regular expression", None, True),
    ]
    _accepted_modes = ("lines", "parts")

    def __init__(self, conf, context):
        super(Grep, self).__init__(conf, context)
        self._re = re.compile(conf["pattern"])

    def _filter(self, text):
        assert isinstance(text, str)
        if self._re.match(text):
            yield text


class Wrap(AbstractFilter):
    """Wrap long lines.

    Params:
        - width: max line len (default=76)
        - max_lines: return at most max_lines
    """
    name = "wrap"
    params = [
        ("mode", "Filtering mode", "lines", True),
        ("width", "Maximal line width", 76, False),
        ("max_lines", "Max number of lines", None, False),
    ]

    def __init__(self, conf, context):
        super(Wrap, self).__init__(conf, context)
        self._tw = textwrap.TextWrapper()

    def filter(self, parts):
        self._tw.text = self.conf.get("width") or 76
        self._tw.max_lines = self.conf.get("max_lines") or None
        return super(Wrap, self).filter(parts)

    def _filter(self, text):
        yield "\n".join(self._tw.fill(line) for line in text.split('\n'))


class DeCSVlise(AbstractFilter):
    """Split csv input into lines"""

    name = "de-csv"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("delimiter", "Field delimiter", ",", False),
        ("quote_char", "character to quote fields", None, False),
        ("generate_parts", "Generate parts instead of split into lines",
         False, False),
        ("strip", "strip whitespaces", False, False),
    ]

    def _filter(self, text):
        reader = csv.reader([text], delimiter=self.conf['delimiter'],
                            quotechar=self.conf['quote_char'])
        if self.conf['strip']:
            convfunc = lambda x: str(x).strip()
        else:
            convfunc = str

        if self.conf['generate_parts']:
            yield from map(convfunc, reader)
        else:
            yield '\n'.join(map(convfunc, list(reader)[0]))


def _get_elements_by_xpath(data, expression):
    if not etree:
        raise common.InputError("module etree not found")
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
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("sel", "selector", None, True),
    ]
    _accepted_modes = ("parts", )

    def validate(self):
        super(GetElementsByCss, self).validate()
        sel = self.conf["sel"]
        from cssselect import GenericTranslator, SelectorError
        try:
            self._expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')

    def _filter(self, text):
        assert isinstance(text, str), repr(text)
        yield from _get_elements_by_xpath(text, self._expression)


class GetElementsByXpath(AbstractFilter):
    """Extract elements from html/xml by xpath selector"""

    name = "get-elements-by-xpath"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("xpath", "selector", None, True),
    ]
    _accepted_modes = ("parts", )

    def _filter(self, text):
        assert isinstance(text, str)
        xpath = self.conf["xpath"]
        yield from _get_elements_by_xpath(text, xpath)


def _get_elements_by_id(data, sel):
    if not etree:
        raise common.InputError("module etree not found")
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
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("sel", "selector", None, True),
    ]
    _accepted_modes = ("parts", )

    def _filter(self, text):
        assert isinstance(text, str)
        sel = self.conf["sel"]
        yield from _get_elements_by_id(text, sel)


class CommandFilter(AbstractFilter):
    """Filter through command"""

    name = "command"
    params = [
        ("mode", "Filtering mode", "parts", True),
        ("command", "command to run", None, True),
    ]

    def _filter(self, text):
        # TODO: convert new line charactes
        assert isinstance(text, str)
        #_LOG.debug("CommandFilter %r, %r", self.conf["command"], text)
        subp = subprocess.Popen(self.conf["command"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                shell=True)

        stdout, stderr = subp.communicate(text.encode('utf-8'))
        res = stdout or stderr or b""
        if res:
            yield res.decode("utf-8")


def get_filter(conf, context):
    """ Get filter object by configuration """
    name = conf.get("name")
    if not name:
        _LOG.warning("missing filter name in: %r", conf)
        return None

    rcls = common.find_subclass(AbstractFilter, name)
    if rcls:
        fltr = rcls(conf, context)
        fltr.validate()
        return fltr

    _LOG.warning("unknown filter: %s", name)
