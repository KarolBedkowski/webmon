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

from flask import (
    Blueprint, url_for, request, abort
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
        group_id = database.groups.find_id_by_feed(db, key)
    except database.NotFound:
        return abort(404)

    feed = AtomFeed('Recent Articles',
                    feed_url=request.url, url=request.url_root)

    for entry in database.entries.find_for_feed(db, group_id):
        body = markdown2.markdown(
            entry.get_summary() if entry.is_long_content() else entry.content,
            extras=["code-friendly", "nofollow", "target-blank-links"])
        _LOG.debug('entry: %s', entry)
        feed.add(entry.title or entry.group.name, body,
                 content_type='html',
                 url=urllib.parse.urljoin(
                     request.url_root,
                     url_for("entry.entry", entry_id=entry.id)),
                 updated=entry.updated,
                 published=entry.created)
    return feed.get_response()
