#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.
#
# based on  https://github.com/nwalsh1995/min-rss-gen

"""
Web gui
"""

import logging
import typing as ty
import urllib
import xml.etree.ElementTree
from datetime import datetime

from flask import Blueprint, Response, abort, request, url_for

from webmon2 import database
from webmon2.web import get_db

_LOG = logging.getLogger(__name__)
BP = Blueprint("atom", __name__, url_prefix="/atom")

DEFAULT_ETREE = xml.etree.ElementTree
ItemElement = ty.NewType("ItemElement", DEFAULT_ETREE.Element)


def add_subelement_with_text(
    root: DEFAULT_ETREE.Element, child_tag: str, text: str
):
    sub = DEFAULT_ETREE.SubElement(root, child_tag)
    sub.text = text
    return sub


# pylint: disable=unused-argument
def gen_item(
    title: ty.Optional[str] = None,
    link: ty.Optional[str] = None,
    description: ty.Optional[str] = None,
    comments: ty.Optional[str] = None,
    pub_date: ty.Optional[str] = None,
) -> ItemElement:

    args = {k: v for k, v in locals().items() if v is not None}
    item = DEFAULT_ETREE.Element("item")
    for tag_name, tag_value in args.items():
        add_subelement_with_text(item, tag_name, tag_value)

    return ItemElement(item)


def start_rss(
    title: str,
    link: str,
    description: str,
    pub_date: ty.Optional[str] = None,
    last_build_date: ty.Optional[str] = None,
    items: ty.Optional[ty.Iterable[ItemElement]] = None,
) -> DEFAULT_ETREE.Element:
    args = {
        k: v
        for k, v in locals().items()
        if v is not None and k not in ("items", "title", "link", "description")
    }

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
def group(key):
    if key == "off":
        return abort(404)

    db = get_db()

    try:
        grp = database.groups.get_by_feed(db, key)
    except database.NotFound:
        return abort(404)
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

    for entry in database.entries.find_for_feed(db, grp.id):
        body = entry.content
        url = urllib.parse.urljoin(
            request.url_root, url_for("entry.entry", entry_id=entry.id)
        )

        rss_items.append(
            gen_item(
                title=entry.title or entry.grp.name,
                link=url,
                description=body,
                pub_date=(
                    entry.updated or entry.created or datetime.now()
                ).isoformat(),
            )
        )

    rss_xml_element = start_rss(
        title="Webmon2 - " + grp.name,
        description="Webmon2 feed for group " + grp.name,
        link=request.url,
        items=rss_items,
        pub_date=updated.isoformat(),
    )

    response = Response(
        xml.etree.ElementTree.tostring(rss_xml_element),
        mimetype="application/atom+xml",
    )
    response.headers["ETag"] = etag
    response.headers["Last-Modified"] = updated
    return response
