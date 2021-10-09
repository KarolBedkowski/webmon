#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Formating entry content functions
"""

import logging
import typing as ty

import lxml
import markdown2
import readability

_LOG = logging.getLogger(__name__)


def format_markdown(body: str) -> str:
    if not body:
        return body

    value = markdown2.markdown(
        body, extras=["code-friendly", "nofollow", "target-blank-links"]
    )
    return value


def format_html(body: str) -> str:
    if not body:
        return body

    if "<body" not in body:
        return body

    doc = readability.Document(body)
    try:
        content = doc.summary(html_partial=True)
        return _clean_html_brutal(content)
    except TypeError as err:
        _LOG.warning("_readable_html summary error: %s", err)
        _LOG.debug("body: %r", body)

    return _clean_html_brutal(body)


def _clean_html_brutal(content):
    body_start = content.find("<body")
    if body_start >= 0:
        body_mark_end = content.find(">", body_start)
        content = content[body_mark_end + 1 :]
        body_end = content.find("</body")
        if body_end > -1:
            content = content[:body_end]

    while True:
        script_start = content.find("<script")
        if script_start < 0:
            break

        script_end = content.find("</script>", script_start)
        if script_end > script_start:
            content = content[:script_start] + content[script_end + 9 :]
        else:
            script_end = content.find("/>", script_start)
            if script_end > script_start:
                content = content[:script_start] + content[script_end + 2 :]
            else:
                # broken
                break

    return content


def body_format(body: str, content_type: str) -> str:
    """FIXME: not in use"""
    if content_type == "html":
        return _clean_html_brutal(body)  # format_html(body)

    if content_type == "preformated":
        return format_html(body)

    return _clean_html_brutal(format_markdown(body))


def sanitize_content(body: str, content_type: str) -> ty.Tuple[str, str]:
    if not body:
        return body, content_type

    result_type = content_type
    if content_type == "html" or content_type.startswith("text/html"):
        body = format_html(body)
        body = _clean_html_brutal(body)
        result_type = "safe"
    elif content_type == "safe":
        body = _clean_html_brutal(body)

    if body:
        body = body.replace("\x00", "")

    return body, result_type


def cleanup_html(content: str) -> str:
    """Try to clean html content from scripts, styles and keep only body part"""
    return _clean_html_brutal(content)


def entry_summary(
    content: ty.Optional[str], content_type: ty.Optional[str]
) -> str:
    if not content:
        return ""

    if content_type not in ("markdown", "plain"):
        document = lxml.html.document_fromstring(content)
        # pylint: disable=c-extension-no-member
        content = "\n".join(lxml.etree.XPath("//text()")(document))

    if len(content) > 400:
        content = "\n".join(content.split("\n", 21)[:20])[:400] + "\n…"

    return content
