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

from flask import request

from webmon2 import formatters

_LOG = logging.getLogger(__name__)


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
    app.jinja_env.filters['format_markdown'] = formatters.format_markdown
    app.jinja_env.filters['age'] = _age_filter
    app.jinja_env.filters['format_date'] = _format_date
    app.jinja_env.filters['absolute_url'] = _absoute_url
    app.jinja_env.filters['format_html'] = formatters.format_html
    app.jinja_env.filters['cleanup_html'] = formatters.cleanup_html
    app.jinja_env.filters['summary'] = formatters.entry_summary
