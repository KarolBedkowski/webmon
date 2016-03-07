#!/usr/bin/python3


class ParamError(RuntimeError):
    pass


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
        conv = h2t.HTML2Text()
        return conv.handle(inp)


class Strip(AbstractFilter):
    """docstring for Strip"""

    name = "strip"

    def filter(self, inp):
       return '\n'.join(line.strip() for line in inp.split("\n"))



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
            raise ParamError("missing 'sel' param")
        try:
            expression = GenericTranslator().css_to_xpath(sel)
        except SelectorError:
            raise ValueError('Invalid CSS selector for filtering')
        return ''.join(_get_elements_by_xpath(inp, expression))


class GetElementsByXpath(AbstractFilter):
    """docstring for GetElementByCss"""

    name = "get-elements-by-xpath"

    def filter(self, inp):
        xpath = self.conf.get("xpath")
        if not xpath:
            raise ParamError("missing 'xpath' parameter")
        return ''.join(_get_elements_by_xpath(inp, xpath))


def get_filter(conf):
    name = conf.get("name")
    for rcls in getattr(AbstractFilter, "__subclasses__")():
        if getattr(rcls, 'name') == name:
            return rcls(conf)
    return None
