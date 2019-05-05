#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Web gui
"""

import logging
import typing as ty
import urllib
from datetime import datetime

from flask import (
    Blueprint, url_for, request, abort, Response
)
from werkzeug.contrib.atom import AtomFeed
import markdown2

from webmon2.web import get_db
from webmon2 import database


_ = ty
_LOG = logging.getLogger(__name__)
BP = Blueprint('atom', __name__, url_prefix='/atom')


@BP.route("/group/<key>")
def group(key):
    db = get_db()

    if key == 'off':
        return abort(404)

    try:
        group = database.groups.get_by_feed(db, key)
    except database.NotFound:
        return abort(404)
    updated_etag = database.groups.get_state(db, group.id)
    _LOG.debug('updated_etag %r', updated_etag)
    if not updated_etag:
        return Response('Not modified', 304)

    db.commit()
    updated, etag = updated_etag

    if request.if_modified_since and request.if_modified_since >= updated:
        _LOG.debug('if_modified_since: %s', request.if_modified_since)
        return Response('Not modified', 304)

    if request.if_match and request.if_match.contains(etag):
        _LOG.debug('if_matche: %s', request.if_match)
        return Response('Not modified', 304)

    feed = AtomFeed("Webmon2 - " + group.name,
                    feed_url=request.url, url=request.url_root,
                    updated=updated)

    for entry in database.entries.find_for_feed(db, group.id):
        is_long = entry.is_long_content()
        body = markdown2.markdown(
            entry.get_summary() if is_long else entry.content,
            extras=["code-friendly", "nofollow", "target-blank-links"])
        feed.add(entry.title or entry.group.name, body,
                 content_type='html',
                 url=urllib.parse.urljoin(
                     request.url_root,
                     url_for("entry.entry", entry_id=entry.id)),
                 updated=entry.updated or entry.created or datetime.now(),
                 published=entry.created)

    response = feed.get_response()
    response.headers['ETag'] = etag
    response.headers['Last-Modified'] = updated
    return response
