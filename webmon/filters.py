#!/usr/bin/python3
"""
Default filters definition.
Filters get one content and transform it to another.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""
import subprocess
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


class AbstractFilter(object):
    """Base class for all filters.

    Mode:
        * parts - filter whole parts
        * lines - filter all lines in each parts
    """

    name = None
    # parameters - list of tuples (name, description, default, required)
    params = [
        ("mode", "Filtering mode", "parts", False),
    ]

    def __init__(self, conf: dict, ctx: common.Context):
        super(AbstractFilter, self).__init__()
        self._ctx = ctx
        self._conf = common.apply_defaults(
            {key: val for key, _, val, _ in self.params},
            conf)

    def validate(self):
        """ Validate filter parameters """
        for name, _, _, required in self.params or []:
            if required and not self._conf.get(name):
                raise common.ParamError("missing parameter " + name)

    def filter(self, result: common.Result):
        # TODO: copy result
        items = []
        for item in result.items:
            items.extend(self._filter(item, result))
        result.items = items
        return result

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        raise NotImplementedError()


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"
    params = [
        ("mode", "Filtering mode", "parts", False),
        ("width", "Max line width", 999999, True),
    ]

    def validate(self):
        super(Html2Text, self).validate()
        width = self._conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid width: %r" % width)

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        assert isinstance(item, common.Item)
        # TODO: handle import error
        import html2text as h2t
        conv = h2t.HTML2Text(bodywidth=self._conf.get("width"))
        # TODO: copy item
        yield item.copy(content=conv.handle(item.content))


class Strip(AbstractFilter):
    """Strip characters from input"""

    name = "strip"
    params = [
        ("chars", "Characters to strip", None, False),
    ]

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        yield item.copy(content=item.content.strip(self._conf['chars']))


class Split(AbstractFilter):
    """Split input on given character"""

    name = "split"
    params = [
        ("separator", "Delimiter string (default \\n)", None, False),
        ("max_split", "Maximum number of lines", -1, False),
        ("generate_parts", "Generate parts instead of split into lines",
         False, False),
    ]

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        sep = self._conf['separator']
        if self._conf['generate_parts']:
            for text in item.content.split(
                    "\n" if sep is None else sep, self._conf['max_split']):
                yield item.copy(content=text)
        else:
            lines = item.content.split("\n" if sep is None else sep,
                                       self._conf['max_split'])
            yield item.copy(content="\n".join(lines))


class Sort(AbstractFilter):
    """ Sort items. """

    name = "sort"
    params = [
        ("mode", "Filtering mode (parts/lines)", "parts", False),
    ]

    def filter(self, result: common.Result):
        # TODO: copy result
        if self._conf['mode'] == "parts":
            result.items.sort()
        else:
            items = [item.copy(content="\n".join(sorted(part.split("\n"))))
                     for item in result.items]
            result.items = items
        return result


class Grep(AbstractFilter):
    """Strip white spaces from input"""

    name = "grep"
    params = [
        ("mode", "Filtering mode (parts/lines)", "parts", False),
        ("pattern", "Regular expression", None, True),
    ]

    def __init__(self, conf, ctx):
        super(Grep, self).__init__(conf, ctx)
        self._re = re.compile(conf["pattern"])

    def filter(self, result: common.Result):
        # TODO: copy result
        if self._conf['mode'] == "parts":
            items = [item for item in result.items
                     if self._re.match(item.content)]
        else:
            items = []
            for item in result.items:
                content = "\n".join(
                    line for line in item.content.split("\n")
                    if self._re.match(line)
                )
                if content:
                    items.append(item.copy(content=content))
        result.items = items
        return result


class Wrap(AbstractFilter):
    """Wrap long lines.

    Params:
        - width: max line len (default=76)
        - max_lines: return at most max_lines
    """
    name = "wrap"
    params = [
        ("width", "Maximal line width", 76, False),
        ("max_lines", "Max number of lines", None, False),
    ]

    def __init__(self, conf, ctx):
        super(Wrap, self).__init__(conf, ctx)
        self._tw = textwrap.TextWrapper(
            break_long_words=False,
            break_on_hyphens=False)

    def filter(self, result: common.Result):
        self._tw.text = self._conf.get("width") or 76
        self._tw.max_lines = self._conf.get("max_lines") or None
        return super(Wrap, self).filter(result)

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        nitem = item.copy()
        nitem.content = "\n".join(
            self._tw.fill(line) for line in item.content.split('\n'))
        yield nitem


def _strip_str(inp):
    return str(inp).strip()


class DeCSVlise(AbstractFilter):
    """Split csv input into lines"""

    name = "de-csv"
    params = [
        ("delimiter", "Field delimiter", ",", False),
        ("quote_char", "character to quote fields", None, False),
        ("generate_parts", "Generate parts instead of split into lines",
         False, False),
        ("strip", "strip whitespaces", False, False),
    ]

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        reader = csv.reader([item.content],
                            delimiter=self._conf['delimiter'],
                            quotechar=self._conf['quote_char'])
        convfunc = _strip_str if self._conf['strip'] else str

        if self._conf['generate_parts']:
            for part in map(convfunc, reader):
                yield item.copy(content=part)
        else:
            yield item.copy(content='\n'.join(map(convfunc, list(reader)[0])))


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
        ("sel", "selector", None, True),
    ]

    def __init__(self, conf, ctx):
        super(GetElementsByCss, self).__init__(conf, ctx)
        self._expression = None

    def validate(self):
        super(GetElementsByCss, self).validate()
        sel = self._conf["sel"]
        from cssselect import GenericTranslator, SelectorError
        try:
            self._expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        for part in _get_elements_by_xpath(item.content, self._expression):
            yield item.copy(content=part)


class GetElementsByXpath(AbstractFilter):
    """Extract elements from html/xml by xpath selector"""

    name = "get-elements-by-xpath"
    params = [
        ("xpath", "selector", None, True),
    ]

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        xpath = self._conf["xpath"]
        for part in _get_elements_by_xpath(item.content, xpath):
            yield item.copy(content=part)


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
        ("sel", "selector", None, True),
    ]

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        sel = self._conf["sel"]
        for part in _get_elements_by_id(item.content, sel):
            yield item.copy(content=part)


class CommandFilter(AbstractFilter):
    """Filter through command"""

    name = "command"
    params = [
        ("mode", "Filtering mode (parts/lines)", "parts", False),
        ("command", "command to run", None, True),
        ("split_lines", "split filter results on newline character",
         False, True),
    ]

    def _filter(self, item: common.Item, result: common.Result) \
            -> common.Result:
        subp = subprocess.Popen(self._conf["command"],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                shell=True)

        stdout, stderr = subp.communicate(item.content.encode('utf-8'))
        res = stdout or stderr or b""
        if res:
            if self._conf['split_lines']:
                for line in res.decode("utf-8").split("\n"):
                    yield item.copy(content=line)
            else:
                yield item.copy(content=res.decode("utf-8"))


def get_filter(conf, ctx: common.Context):
    """ Get filter object by configuration """
    name = conf.get("name")
    if not name:
        ctx.log_error("missing filter name: %r", conf)
        return None

    rcls = common.find_subclass(AbstractFilter, name)
    if rcls:
        fltr = rcls(conf, ctx)
        fltr.validate()
        return fltr

    ctx.log_error("unknown filter: %s", name)
    return None
