# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.
#
# based on  https://github.com/nwalsh1995/min-rss-gen

"""
Web gui
"""
from __future__ import annotations

import logging
import typing as ty
import urllib
import xml.etree.ElementTree
from datetime import datetime, timezone

from flask import Blueprint, Response, abort, request, url_for

from webmon2 import database

from . import _commons as c

_LOG = logging.getLogger(__name__)
BP = Blueprint("atom", __name__, url_prefix="/atom")

DEFAULT_ETREE = xml.etree.ElementTree
ItemElement = ty.NewType("ItemElement", DEFAULT_ETREE.Element)


def add_subelement_with_text(
    root: DEFAULT_ETREE.Element, child_tag: str, text: str
) -> DEFAULT_ETREE.Element:
    sub = DEFAULT_ETREE.SubElement(root, child_tag)
    sub.text = text
    return sub


# pylint: disable=unused-argument
def gen_item(
    title: str | None = None,
    link: str | None = None,
    description: str | None = None,
    comments: str | None = None,
    args: dict[str, ty.Any] | None = None,
) -> ItemElement:
    args = args or {}
    item = DEFAULT_ETREE.Element("item")
    for tag_name, tag_value in args.items():
        add_subelement_with_text(item, tag_name, tag_value)

    return ItemElement(item)


def start_rss(
    title: str,
    link: str,
    description: str,
    items: ty.Iterable[ItemElement] | None = None,
    args: dict[str, ty.Any] | None = None,
) -> DEFAULT_ETREE.Element:
    args = args or {}
    rss = DEFAULT_ETREE.Element("rss", version="2.0")
    channel = DEFAULT_ETREE.SubElement(rss, "channel")

    add_subelement_with_text(channel, "title", title)
    add_subelement_with_text(channel, "link", link)
    add_subelement_with_text(channel, "description", description)

    for atitle, value in args.items():
        add_subelement_with_text(channel, atitle, value)

    if items is not None:
        channel.extend(items)

    return rss


@BP.route("/group/<key>")
def group(key: str) -> Response:
    if key == "off":
        return abort(404)

    db = c.get_db()

    try:
        grp = database.groups.get_by_feed(db, key)
    except database.NotFound:
        return abort(404)

    assert grp and grp.id
    updated_etag = database.groups.get_state(db, grp.id)
    _LOG.debug("updated_etag %r", updated_etag)
    if not updated_etag:
        return Response("Not modified", 304)

    db.commit()
    updated, etag = updated_etag

    if request.if_modified_since and request.if_modified_since >= updated:
        _LOG.debug("if_modified_since: %s", request.if_modified_since)
        return Response("Not modified", 304)

    if request.if_match and request.if_match.contains(etag):
        _LOG.debug("if_matche: %s", request.if_match)
        return Response("Not modified", 304)

    rss_items = []

    for entry in database.entries.find_for_feed(db, grp.user_id, grp.id):
        body = entry.content
        url = urllib.parse.urljoin(
            request.url_root, url_for("entry.entry", entry_id=entry.id)
        )

        rss_items.append(
            gen_item(
                title=entry.title or entry.source.group.name,
                link=url,
                description=body,
                args={
                    "pubDate": (
                        entry.updated
                        or entry.created
                        or datetime.now(timezone.utc)
                    ).isoformat()
                },
            )
        )

    rss_xml_element = start_rss(
        title="Webmon2 - " + grp.name,
        description="Webmon2 feed for group " + grp.name,
        link=request.url,
        items=rss_items,
        args={"pubDate": updated.isoformat()},
    )

    response = Response(
        xml.etree.ElementTree.tostring(rss_xml_element),
        mimetype="application/atom+xml",
    )
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = updated.isoformat()
    return response
