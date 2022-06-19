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
import typing as ty
import urllib
from zoneinfo import ZoneInfo

import lxml
import lxml.html
from flask import Flask, request, session, url_for
from flask_babel import format_datetime, gettext

from webmon2 import formatters

_LOG = logging.getLogger(__name__)


def _age_filter(date: ty.Optional[datetime.datetime]) -> str:
    if date is None:
        return ""

    diff = (
        datetime.datetime.now(datetime.timezone.utc) - date
    ).total_seconds()
    if diff < 60:
        return "<1m"

    if diff < 3600:  # < 1h
        return str(int(diff // 60)) + "m"

    if diff < 86400:  # < 1d
        return str(int(diff // 3600)) + "h"

    return str(int(diff // 86400)) + "d"


def _format_date(date: ty.Any) -> str:
    if date is None:
        return gettext("none")

    if isinstance(date, datetime.datetime):
        if user_tz := session.get("_user_tz"):
            date = date.astimezone(ZoneInfo(user_tz))

        return format_datetime(date)

    return str(date)


def _absoute_url(url: str) -> str:
    return urllib.parse.urljoin(request.url_root, url)


def _entry_score_class(score: int) -> str:
    """Get class name for entry score."""
    if score < -5:
        return "prio-lowest"
    if score < 0:
        return "prio-low"
    if score > 5:
        return "prio-highest"
    if score > 0:
        return "prio-high"

    return ""


def _format_key(inp: str) -> str:
    if not inp:
        return ""

    inp = inp.replace("_", " ")
    return inp[0].upper() + inp[1:]


def _proxy_links(content: str) -> str:
    """Replace links to img/other objects to local proxy."""
    document = lxml.html.document_fromstring(content)
    changed = False
    for node in document.xpath("//img"):
        src = node.attrib.get("src")
        if src and src.startswith("http"):
            node.attrib["src"] = url_for("proxy.proxy", path=src)
            changed = True

    if not changed:
        return content

    return lxml.etree.tostring(document).decode("utf-8")


def register(app: Flask) -> None:
    app.jinja_env.filters["format_markdown"] = formatters.format_markdown
    app.jinja_env.filters["age"] = _age_filter
    app.jinja_env.filters["format_date"] = _format_date
    app.jinja_env.filters["absolute_url"] = _absoute_url
    app.jinja_env.filters["format_html"] = formatters.format_html
    app.jinja_env.filters["cleanup_html"] = formatters.cleanup_html
    app.jinja_env.filters["summary"] = formatters.entry_summary
    app.jinja_env.filters["entry_score_class"] = _entry_score_class
    app.jinja_env.filters["format_key"] = _format_key

    app_conf = app.config["app_conf"]
    if app_conf.getboolean("web", "proxy_media"):
        app.jinja_env.filters["proxy_links"] = _proxy_links
    else:
        app.jinja_env.filters["proxy_links"] = lambda x: x
