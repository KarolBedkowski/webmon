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

import markdown2
import readability


_LOG = logging.getLogger(__file__)


def format_markdown(body: str) -> str:
    if not body:
        return body
    value = markdown2.markdown(body, extras=["code-friendly", "nofollow",
                                             "target-blank-links"])
    return value


def format_html(body: str) -> str:
    if not body:
        return body
    if '<body' not in body:
        return body
    doc = readability.Document(body)
    try:
        return doc.get_clean_html()
    except TypeError:
        _LOG.exception("_readable_html error: %r", body)
    return body


def body_format(body: str, content_type: str) -> str:
    if content_type == 'html':
        return format_html(body)
    if content_type == 'preformated':
        return body
    return format_markdown(body)
