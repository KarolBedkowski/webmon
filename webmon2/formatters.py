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
from werkzeug.contrib.cache import SimpleCache

_LOG = logging.getLogger(__name__)
_BODY_CACHE = SimpleCache(threshold=50, default_timeout=300)


def format_markdown(body: str) -> str:
    if not body:
        return body
    body_hash = hash(body)
    value = _BODY_CACHE.get(body_hash)
    if value is not None:
        return value
    value = markdown2.markdown(body, extras=["code-friendly", "nofollow",
                                             "target-blank-links"])
    _BODY_CACHE.set(body_hash, value)
    return value


def format_html(body: str) -> str:
    if not body:
        return body
    if '<body' not in body:
        return body
    body_hash = hash(body)
    value = _BODY_CACHE.get(body_hash)
    if value is not None:
        return value
    value = _BODY_CACHE.get(body_hash)
    doc = readability.Document(body)
    try:
        content = doc.get_clean_html()
        _BODY_CACHE.set(body_hash, content)
        return content
    except TypeError:
        _LOG.exception("_readable_html error: %r", body)
    try:
        content = doc.summary(html_partial=True)
        _BODY_CACHE.set(body_hash, content)
        return content
    except TypeError:
        _LOG.exception("_readable_html error: %r", body)

    return body


def body_format(body: str, content_type: str) -> str:
    if content_type == 'html':
        return body  # format_html(body)
    if content_type == 'preformated':
        return format_html(body)
    return format_markdown(body)


def sanitize_content(body: str, content_type: str) -> str:
    if content_type == 'html':
        return format_html(body)
    return body
