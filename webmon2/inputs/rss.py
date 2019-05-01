#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
RSS data loader
"""
import logging
import typing as ty
import time
import datetime

import feedparser

from webmon2 import common, model

from .abstract import AbstractInput


_LOG = logging.getLogger(__file__)
_ = ty
_RSS_DEFAULT_FIELDS = "title, updated_parsed, published_parsed, link, author"


class RssInput(AbstractInput):
    """ Load data from rss
    """
    name = "rss"
    params = AbstractInput.params + [
        ("url", "RSS xml url", None, True, None, str),
        ("max_items", "Maximal number of articles to load", None, False, None,
         int),
        ("load_content", "Load content of entries", False, False, None, bool),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """ Return rss items as one or many parts; each part is on article. """
        new_state, entries = self._load(state)
        if new_state.status != 'error':
            new_state.next_update = datetime.datetime.now() + \
                datetime.timedelta(
                    seconds=common.parse_interval(self._source.interval))
        return new_state, entries

    def _load(self, state: model.SourceState):
        # pylint: disable=too-many-locals
        feedparser.PARSE_MICROFORMATS = 0
        feedparser.USER_AGENT = "Mozilla/5.0 (X11; Linux i686; rv:45.0) " \
                                "Gecko/20100101 Firefox/45.0"
        doc = feedparser.parse(
            self._conf['url'],
            etag=state.get_state('etag'),
            modified=state.last_update)
        status = doc.get('status') if doc else 400
        if status not in (200, 301, 302, 304):
            return _fail_error(state, doc, status)

        entries = doc.get('entries')
        entries = [entry for entry in entries
                   if time.mktime(entry.updated_parsed)
                   > state.last_update.timestamp()]
        if status == 304 or not entries:
            new_state = state.new_not_modified()
            new_state.set_state('etag', doc.get('etag'))
            return new_state, []

        new_state = state.new_ok()
        new_state.set_state('etag', doc.get('etag'))

        if status == 301:  # permanent redirects
            new_state.set_state("info", 'Permanently redirects: ' + doc.href)
        elif status == 302:
            new_state.set_state('info', 'Temporary redirects: ' + doc.href)

        load_content = self._conf['load_content']
        items = [self._load_entry(entry, load_content)
                 for entry in self._limit_items(entries)]

        return new_state, items

    def _limit_items(self, entries):
        max_items = self._conf.get("max_items")
        if max_items and len(entries) > max_items:
            entries = entries[:max_items]
        return entries

    def _load_entry(self, entry, load_content):
        result = model.Entry.for_source(self._source)
        result.url = _get_val(entry, 'link')
        result.title = _get_val(entry, 'title')
        result.updated = _get_val(entry, 'updated_parsed')
        result.created = _get_val(entry, 'published_parsed')
        result.status = ('updated' if result.updated > result.created
                         else 'new')
        if load_content:
            result.content = _get_content_from_rss_entry(entry)
        return result


def _fail_error(state, doc, status):
    _LOG.error("load document error %s: %s", status, doc)
    summary = "Loading page error: %s" % status
    feed = doc.get('feed')
    if feed:
        summary = feed.get('summary') or summary
    return state.new_error(summary), []


def _get_content_from_rss_entry(entry):
    content = entry.get('summary')
    if not content:
        content = entry['content'][0].value if 'content' in entry \
            else entry.get('value')
    return content


def _get_val(entry, key):
    val = entry.get(key)
    if isinstance(val, time.struct_time):
        return datetime.datetime.fromtimestamp(time.mktime(val))
    return str(val).strip()
