# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
RSS data loader
"""
from __future__ import annotations

import datetime
import logging
import time
import typing as ty
from contextlib import suppress
from urllib.parse import urljoin

import feedparser
import requests
from flask_babel import gettext, lazy_gettext

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
_ = ty
_RSS_DEFAULT_FIELDS = "title, updated_parsed, published_parsed, link, author"


# feedparser.PARSE_MICROFORMATS = 0
feedparser.USER_AGENT = AbstractSource.AGENT


class RssSource(AbstractSource):
    """Load data from rss"""

    name = "rss"
    short_info = lazy_gettext("RSS/Atom channel")
    long_info = lazy_gettext(
        "Load data form RSS/Atom channel. Require define URL."
    )
    params = AbstractSource.params + [
        common.SettingDef("url", lazy_gettext("RSS XML URL"), required=True),
        common.SettingDef(
            "max_items",
            lazy_gettext("Maximal number of articles to load"),
            value_type=int,
        ),
        common.SettingDef(
            "load_content",
            lazy_gettext("Load content of entries"),
            default=False,
        ),
        common.SettingDef(
            "load_article", lazy_gettext("Load article"), default=False
        ),
    ]  # type: list[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> tuple[model.SourceState, model.Entries]:
        """Return rss items as one or many parts; each part is on article."""
        try:
            new_state, entries = self._load(state)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("source %d load error: %s", state.source_id, err)
            new_state, entries = state.new_error(str(err)), []

        if new_state.status != model.SourceStateStatus.ERROR:
            if entries and new_state.icon:
                for entry in entries:
                    entry.icon = new_state.icon

            assert self._source.interval is not None
            # next update is bigger of now + interval or expire (if set)
            next_update = datetime.datetime.now(
                datetime.timezone.utc
            ) + datetime.timedelta(
                seconds=common.parse_interval(self._source.interval)
            )
            new_state.next_update = max(
                new_state.next_update or next_update, next_update
            )

        return new_state, entries

    def _load(
        self, state: model.SourceState
    ) -> tuple[model.SourceState, list[model.Entry]]:
        # pylint: disable=too-many-locals
        doc = feedparser.parse(
            self._conf["url"],
            etag=state.get_prop("etag"),
            modified=state.last_update,
        )
        status = doc.get("status") if doc else 400
        if status not in (200, 301, 302, 304):
            res = _fail_error(state, doc, status)
            del doc
            doc = None
            return res

        # self._check_sy_updateperiod(doc.feed)

        with suppress(KeyError):
            # pylint: disable=unsubscriptable-object
            self._update_source(web_url=doc["feed"]["link"])

        entries = doc.get("entries")
        if state.last_update:
            entries = list(
                _filter_entries_updated(entries, state.last_update.timestamp())
            )

        if status == 304 or not entries:
            new_state = state.new_not_modified(etag=doc.get("etag"))
            if not new_state.icon:
                new_state.set_icon(self._load_image(doc))

            del doc
            doc = None
            return new_state, []

        new_state = state.new_ok(etag=doc.get("etag"))
        if not new_state.icon:
            new_state.set_icon(self._load_image(doc))

        expires = common.parse_http_date(doc.headers.get("expires"))
        if expires:
            new_state.next_update = expires
            new_state.set_prop("expires", str(expires))

        if status == 301:  # permanent redirects
            new_state.set_prop(
                "info", gettext("Permanently redirects: %(url)s", url=doc.href)
            )
            self._update_source(new_url=doc.href)
        elif status == 302:
            new_state.set_prop(
                "info", gettext("Temporary redirects: %(url)s", url=doc.href)
            )
            self._update_source(new_url=doc.href)
        else:
            new_state.del_prop("info")

        load_article = self._conf["load_article"]
        load_content = self._conf["load_content"]
        with requests.Session() as sess:
            items = [
                self._load_entry(entry, load_content, load_article, sess)
                for entry in self._limit_items(entries)
            ]

        del doc
        return new_state, items

    def _limit_items(self, entries: list[model.Entry]) -> list[model.Entry]:
        max_items = self._conf.get("max_items")
        if max_items:
            max_items = int(max_items)
            if max_items and len(entries) > max_items:
                entries = entries[:max_items]

        return entries

    def _load_entry(
        self,
        entry: feedparser.FeedParserDict,
        load_content: bool,
        load_article: bool,
        sess: requests.Session,
    ) -> model.Entry:
        now = datetime.datetime.now(datetime.timezone.utc)
        result = model.Entry.for_source(self._source)
        result.url = _get_val_str(entry, "link")
        result.title = _get_val_str(entry, "title")
        result.updated = _get_val_dt(entry, "updated_parsed", now)
        result.created = _get_val_dt(entry, "published_parsed", now)
        result.status = model.EntryStatus.NEW
        if load_article:
            result = self._load_article(result, sess)
        elif load_content:
            result.content = entry.get("summary") or (
                entry["content"][0].value
                if "content" in entry
                else entry.get("value")
            )
            result.set_opt("content-type", "html")

        return result

    def _load_article(
        self, entry: model.Entry, sess: requests.Session
    ) -> model.Entry:
        if not entry.url:
            return entry
        response = None
        try:
            response = sess.request(
                url=entry.url,
                method="GET",
                headers={"User-agent": self.AGENT},
                allow_redirects=True,
            )
            if response:
                response.raise_for_status()
                if response.status_code == 200:
                    content_type = response.headers["content-type"]
                    if content_type.startswith("text/"):
                        entry.content = response.text
                        entry.set_opt("content-type", content_type)
                    else:
                        entry.content = gettext(
                            "Article not loaded because of content type: "
                            "%(type)s",
                            type=content_type,
                        )
                else:
                    entry.content = "Loading article error: " + response.text

        except Exception as err:  # pylint: disable=broad-except
            entry.content = gettext("Loading article error: %(err)s", err=err)
        finally:
            if response:
                response.close()
                del response
                response = None

        return entry

    @classmethod
    def to_opml(cls, source: model.Source) -> dict[str, ty.Any]:
        assert source.settings is not None
        return {
            "text": source.name,
            "title": source.name,
            "type": "rss",
            "xmlUrl": source.settings["url"],
        }

    @classmethod
    def from_opml(cls, opml_node: dict[str, ty.Any]) -> model.Source | None:
        url = opml_node["xmlUrl"]
        if not url:
            raise ValueError("missing xmlUrl")

        name = opml_node.get("text") or opml_node["title"]
        if not name:
            raise ValueError("missing text/title")

        src = model.Source(kind="rss", name=name, user_id=0, group_id=0)
        src.settings = {"url": url}
        return src

    def _load_image(
        self, doc: feedparser.FeedParserDict
    ) -> tuple[str, bytes] | None:
        _LOG.debug("source %d load image", self._source.id)
        feed = doc.feed
        image_href = None
        image = feed.get("image")
        if image:
            image_href = image.get("href") or image.get("url")

        if not image_href:
            link = feed.get("link")
            if link:
                image_href = urljoin(link, "favicon.ico")

        return self._load_binary(image_href) if image_href else None

    def _check_sy_updateperiod(self, feed: feedparser.FeedParserDict) -> None:
        if self._source.interval:
            return

        sy_updateperiod = feed.get("sy_updateperiod")
        sy_updatefrequency = feed.get("sy_updatefrequency")
        if not sy_updatefrequency or not sy_updateperiod:
            return

        interval = sy_updateperiod + sy_updatefrequency[0]
        try:
            if common.parse_interval(interval):
                self._update_source(interval=interval)
        except ValueError:
            _LOG.debug(
                "wrong sy_update*: %r %r", sy_updateperiod, sy_updatefrequency
            )

    def _update_source(
        self,
        new_url: str | None = None,
        web_url: str | None = None,
        interval: str | None = None,
    ) -> None:
        assert self._source.settings is not None

        if new_url and new_url != self._source.settings.get("url"):
            self._updated_source = self._updated_source or self._source.clone()
            assert self._updated_source.settings is not None
            self._updated_source.settings["url"] = new_url

        if interval and interval != self._source.interval:
            _LOG.debug("interval updated: %s", interval)
            self._updated_source = self._updated_source or self._source.clone()
            self._updated_source.interval = interval

        if web_url and web_url != self._source.settings.get("web_url"):
            self._updated_source = self._updated_source or self._source.clone()
            assert self._updated_source.settings is not None
            self._updated_source.settings["web_url"] = web_url


def _fail_error(
    state: model.SourceState, doc: feedparser.FeedParserDict, status: int
) -> tuple[model.SourceState, list[model.Entry]]:
    _LOG.error("load document error %r: state: %r %r", status, state, doc)
    summary = gettext("Loading page error: %(status)s", status=status)
    feed = doc.get("feed")
    if feed:
        summary = feed.get("summary") or summary

    return state.new_error(summary), []


def _get_val_str(
    entry: dict[str, ty.Any], key: str, default: str | None = None
) -> str | None:
    val = entry.get(key)
    if val is None:
        return default

    return str(val).strip()


def _get_val_dt(
    entry: dict[str, ty.Any],
    key: str,
    default: datetime.datetime | None = None,
) -> datetime.datetime | None:
    val = entry.get(key)
    if val is None:
        return default

    if isinstance(val, time.struct_time):
        with suppress(ValueError):
            return datetime.datetime.fromtimestamp(
                time.mktime(val), datetime.timezone.utc
            )

    return default


def _filter_entries_updated(
    entries: ty.Iterable[feedparser.FeedParserDict], timestamp: float
) -> ty.Iterable[feedparser.FeedParserDict]:
    now = time.localtime(time.time())
    for entry in entries:
        updated_parsed = entry.get("updated_parsed")
        if not updated_parsed:
            entry["updated_parsed"] = now
            yield entry

        try:
            assert updated_parsed is not None
            if time.mktime(updated_parsed) > timestamp:
                yield entry
        except (ValueError, TypeError):
            entry["updated_parsed"] = now
            yield entry
