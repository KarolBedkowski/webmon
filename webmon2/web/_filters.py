# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Template filters
"""
from __future__ import annotations

import datetime
import logging
import typing as ty
import urllib
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import lxml
import lxml.html
from flask import Flask, request, session, url_for
from flask_babel import format_datetime, gettext

from webmon2 import formatters, model

_LOG = logging.getLogger(__name__)


def _age_filter(date: datetime.datetime | None) -> str:
    if date is None:
        return ""

    diff = int(
        (datetime.datetime.now(datetime.timezone.utc) - date).total_seconds()
    )
    if diff < 60:
        return "<1m"

    if diff < 3600:  # < 1h
        return str(int(diff // 60)) + "m"

    if diff < 86400:  # < 1d
        return str(int(diff // 3600)) + "h"

    return str(int(diff // 86400)) + "d"


def _format_date(date: ty.Any) -> str:
    if date is None:
        return gettext("none")  # type: ignore

    if isinstance(date, datetime.datetime):
        if user_tz := session.get("_user_tz"):
            date = date.astimezone(ZoneInfo(user_tz))

        return format_datetime(date)  # type: ignore

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


def _create_proxy_url(url: str, entry_url: str | None = None) -> str:
    """Create proxied link; if url is relative, use entry.url as base."""
    if not url:
        return ""

    if url.startswith(("http://", "https://")):
        return url_for("proxy.proxy", path=url)

    # handle related urls
    if not entry_url:
        return url

    url = urljoin(entry_url, url)
    return url_for("proxy.proxy", path=url)


def _extract_prefix_postfix(instr: str) -> tuple[str, int, int]:
    prefix = len(instr)

    for num, char in enumerate(instr):
        print(2, num, repr(char))
        if char != " ":
            prefix = num
            break

    instr = instr[prefix:]
    postfix = len(instr)

    for num, char in enumerate(reversed(instr)):
        if char != " ":
            postfix = num
            break

    if postfix:
        instr = instr[:-postfix]

    return instr, prefix, postfix


def _apply_prefix_postfix(instr: str, prefix: int, postfix: int) -> str:
    return (" " * prefix) + instr + (" " * postfix)


def _create_proxy_urls_srcset(
    srcset: str, entry_url: str | None = None
) -> ty.Iterable[str]:
    """Create proxied links from srcset.
    Preserve spaces.

    srcset is in form srcset="<url>" or
    srcset="<url> <size>, <url> <size>, ..."

    """
    for part in srcset.split(","):
        if not part:
            yield ""
            continue

        part, prefix, postfix = _extract_prefix_postfix(part)
        url, sep, size = part.partition(" ")
        url = _create_proxy_url(url, entry_url)
        url = _apply_prefix_postfix(url, prefix, postfix)
        yield f"{url}{sep}{size}"


def _proxy_links(content: str, entry: model.Entry | None = None) -> str:
    """Replace links to img/other objects to local proxy."""
    document = lxml.html.document_fromstring(content)
    changed = False
    entry_url = entry.url if entry else None

    for node in document.xpath("//img"):
        src = node.attrib.get("src")
        res = _create_proxy_url(src, entry_url)
        if src != res:
            node.attrib["src"] = res
            node.attrib["org_src"] = src
            changed = True

    for node in document.xpath("//source"):
        src = node.attrib.get("srcset")
        res = ",".join(_create_proxy_urls_srcset(src, entry_url))
        if res != src:
            node.attrib["srcset"] = res
            node.attrib["org_srcset"] = src
            changed = True

    if not changed:
        return content

    return lxml.etree.tostring(document).decode("utf-8")  # type:ignore


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
        app.jinja_env.filters["proxy_links"] = lambda x, y=None: x
