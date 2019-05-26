#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
RSS data loader
"""
import logging
import typing as ty
import time
import datetime
from urllib.parse import urljoin

import feedparser
import requests

from webmon2 import common, model

from .abstract import AbstractSource


_LOG = logging.getLogger(__name__)
_ = ty
_RSS_DEFAULT_FIELDS = "title, updated_parsed, published_parsed, link, author"


# feedparser.PARSE_MICROFORMATS = 0
feedparser.USER_AGENT = AbstractSource.AGENT


class RssSource(AbstractSource):
    """ Load data from rss
    """
    name = "rss"
    short_info = "RSS/Atom channel"
    long_info = 'Load data form RSS/Atom channel. Require define url.'
    params = AbstractSource.params + [
        common.SettingDef("url", "RSS xml url", required=True),
        common.SettingDef("max_items", "Maximal number of articles to load",
                          value_type=int),
        common.SettingDef("load_content", "Load content of entries",
                          default=False),
        common.SettingDef("load_article", "Load article", default=False),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """ Return rss items as one or many parts; each part is on article. """
        try:
            new_state, entries = self._load(state)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("source %d load error: %s", state.source_id, err)
            new_state, entries = state.new_error(str(err)), []
        if new_state.status != 'error':
            new_state.next_update = datetime.datetime.now() + \
                datetime.timedelta(
                    seconds=common.parse_interval(self._source.interval))
        return new_state, entries

    def _load(self, state: model.SourceState) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        # pylint: disable=too-many-locals
        doc = feedparser.parse(
            self._conf['url'], etag=state.get_state('etag'),
            modified=state.last_update)
        status = doc.get('status') if doc else 400
        if status not in (200, 301, 302, 304):
            return _fail_error(state, doc, status)

        entries = doc.get('entries')
        if state.last_update:
            entries = list(_filter_entries_updated(
                entries, state.last_update.timestamp()))
        if status == 304 or not entries:
            new_state = state.new_not_modified()
            new_state.set_state('etag', doc.get('etag'))
            if not new_state.icon:
                new_state.set_icon(self._load_image(doc))
            return new_state, []

        new_state = state.new_ok()
        new_state.set_state('etag', doc.get('etag'))
        if not new_state.icon:
            new_state.set_icon(self._load_image(doc))

        expires = common.parse_http_date(doc.headers.get('expires'))
        if expires:
            new_state.next_update = expires
            new_state.set_state('expires', str(expires))

        if status == 301:  # permanent redirects
            new_state.set_state("info", 'Permanently redirects: ' + doc.href)
            self._update_source(new_url=doc.href)
        elif status == 302:
            new_state.set_state('info', 'Temporary redirects: ' + doc.href)
            self._update_source(new_url=doc.href)

        load_article = self._conf['load_article']
        load_content = self._conf['load_content']
        items = [self._load_entry(entry, load_content, load_article)
                 for entry in self._limit_items(entries)]

        if items and new_state.icon:
            for item in items:
                item.icon = new_state.icon

        return new_state, items

    def _limit_items(self, entries: ty.List[model.Entry]) \
            -> ty.List[model.Entry]:
        max_items = self._conf.get("max_items")
        if max_items:
            max_items = int(max_items)
            if max_items and len(entries) > max_items:
                entries = entries[:max_items]
        return entries

    def _load_entry(self, entry: feedparser.FeedParserDict,
                    load_content: bool, load_article: bool) \
            -> model.Entry:
        now = datetime.datetime.now()
        result = model.Entry.for_source(self._source)
        result.url = _get_val(entry, 'link')
        result.title = _get_val(entry, 'title')
        result.updated = _get_val(entry, 'updated_parsed') or now
        result.created = _get_val(entry, 'published_parsed') or now
        result.status = 'updated' if result.updated > result.created else 'new'
        if load_article:
            result = self._load_article(result)
        elif load_content:
            content = entry.get('summary')
            if not content:
                content = entry['content'][0].value if 'content' in entry \
                    else entry.get('value')
            result.content = content
            # TODO: detect content (?)
            result.set_opt("content-type", "html")
        return result

    # pylint: disable=no-self-use
    def _load_article(self, entry: model.Entry) -> model.Entry:
        if not entry.url:
            return entry
        try:
            response = requests.request(
                url=entry.url, method='GET',
                headers={"User-agent": self.AGENT},
                allow_redirects=True)
            if response:
                response.raise_for_status()
                if response.status_code == 200:
                    entry.content = response.text
                    entry.set_opt("content-type", "html")
                else:
                    entry.content = "Loading article error: " + response.text
        except Exception as err:  # pylint: disable=broad-except
            entry.content = "Loading article error: " + str(err)
        return entry

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        return {
            'text': source.name,
            'title': source.name,
            'type': 'rss',
            'xmlUrl': source.settings['url'],
        }

    @classmethod
    def from_opml(cls, opml_node: ty.Dict[str, ty.Any]) \
            -> ty.Optional[model.Source]:
        url = opml_node['xmlUrl']
        if not url:
            raise ValueError('missing xmlUrl')
        name = opml_node.get('text') or opml_node['title']
        if not name:
            raise ValueError('missing text/title')
        return model.Source(
            kind='rss',
            name=name,
            settings={'url': url}
        )

    def _load_image(self, feed):
        image_href = None
        image = feed.get('image')
        if image:
            image_href = image.get('href') or image.get('url')

        if not image_href:
            link = feed.get('link')
            if link:
                image_href = urljoin(link, 'favicon.ico')

        return self._load_binary(image_href) if image_href else None

    def _update_source(self, new_url=None):
        if not self._updated_source:
            self._updated_source = self._source.clone()
        if new_url:
            self._updated_source.settings['url'] = new_url


def _fail_error(state: model.SourceState, doc, status: int) \
            -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
    _LOG.error("load document error %s: %s", status, doc)
    summary = f"Loading page error: {status}"
    feed = doc.get('feed')
    if feed:
        summary = feed.get('summary') or summary
    return state.new_error(summary), []


def _get_val(entry, key: str):
    val = entry.get(key)
    if val is None:
        return None
    if isinstance(val, time.struct_time):
        try:
            return datetime.datetime.fromtimestamp(time.mktime(val))
        except ValueError:
            return None
    return str(val).strip()


def _filter_entries_updated(entries, timestamp):
    now = time.localtime(time.time())
    for entry in entries:
        updated_parsed = entry.get('updated_parsed')
        if not updated_parsed:
            entry['updated_parsed'] = now
            yield entry
        try:
            if time.mktime(updated_parsed) > timestamp:
                yield entry
        except (ValueError, TypeError):
            entry['updated_parsed'] = now
            yield entry
