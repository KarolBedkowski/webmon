#!/usr/bin/python3


class ParamError(RuntimeError):
    pass


def html2text(inp, **opts):
    """docstring for html2text"""
    import html2text as h2t
    conv = h2t.HTML2Text()
    return conv.handle(inp)


def strip(inp, **opts):
    return '\n'.join(line.strip() for line in inp.split("\n"))


def _get_elements_by_xpath(data, expression):
    from lxml import etree

    html_parser = etree.HTMLParser(encoding='utf-8', recover=True,
                                   strip_cdata=True)
    document = etree.fromstringlist([data], html_parser)
    for e in document.xpath(expression):
        if isinstance(e, etree._Element):
            text = etree.tostring(e)
        else:
            text = str(e)
        if text:
            yield text.decode('utf-8')


def get_elements_by_css(inp, **opts):
    from cssselect import GenericTranslator, SelectorError

    sel = opts.get("sel")
    if not sel:
        raise ParamError("missing 'sel' param")
    try:
        expression = GenericTranslator().css_to_xpath(sel)
    except SelectorError:
        raise ValueError('Invalid CSS selector for filtering')
    return ''.join(_get_elements_by_xpath(inp, expression))


def get_elements_by_xpath(inp, **opts):
    xpath = opts.get("xpath")
    if not xpath:
        raise ParamError("missing 'xpath' parameter")
    return ''.join(_get_elements_by_xpath(inp, xpath))


_FILTERS = {
    "html2text": html2text,
    "strip": strip,
    "get-elements-by-xpath": get_elements_by_xpath,
    "get-elements-by-css": get_elements_by_css,
}


def get_filter(conf):
    name = conf.get("name")
    return _FILTERS[name]
