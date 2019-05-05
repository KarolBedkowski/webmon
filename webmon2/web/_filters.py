#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Template filters
"""
import datetime
import logging
import urllib

import markdown2
from werkzeug.contrib.cache import SimpleCache
from flask import request
import readability


_LOG = logging.getLogger(__file__)
_BODY_CACHE = SimpleCache(threshold=50, default_timeout=300)


def _format_body_filter(body):
    if not body:
        return body
    body_hash = hash(body)
    value = _BODY_CACHE.get(body_hash)
    if value is not None:
        _LOG.debug("format_body cache hit")
        return value
#    return publish_parts(
#        body, writer_name='html', settings=None)['fragment']
    value = markdown2.markdown(body, extras=["code-friendly", "nofollow",
                                             "target-blank-links"])
    _BODY_CACHE.set(body_hash, value)
    return value


def _readable_html(body):
    if not body:
        return body
    doc = readability.Document(body)
    return doc.get_clean_html()


def _age_filter(date):
    if date is None:
        return ""
    diff = (datetime.datetime.now() - date).total_seconds()
    if diff < 60:
        return '<1m'
    if diff < 3600:  # < 1h
        return str(int(diff//60)) + "m"
    if diff < 86400:  # < 1d
        return str(int(diff//3600)) + "h"
    return str(int(diff//86400)) + "d"


def _format_date(date):
    if isinstance(date, datetime.datetime):
        return date.strftime("%x %X")
    return date


def _absoute_url(url):
    return urllib.parse.urljoin(request.url_root, url)


def register(app):
    app.jinja_env.filters['format_body'] = _format_body_filter
    app.jinja_env.filters['age'] = _age_filter
    app.jinja_env.filters['format_date'] = _format_date
    app.jinja_env.filters['absolute_url'] = _absoute_url
    app.jinja_env.filters['readable_html'] = _readable_html
