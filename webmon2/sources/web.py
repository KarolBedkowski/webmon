#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Load data from webpage
"""
import datetime
import email.utils
import logging
import typing as ty
from urllib.parse import urlsplit, urlunsplit

import requests

from webmon2 import common, model

from .abstract import AbstractSource

_ = ty
_LOG = logging.getLogger(__name__)


class WebSource(AbstractSource):
    """Load data from web (http/https)"""

    name = "url"
    short_info = "Web page"
    long_info = "Load data form web page pointed by url."
    params = AbstractSource.params + [
        common.SettingDef("url", "Web page url", required=True),
        common.SettingDef("timeout", "loading timeout", default=30),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        """Return one part - page content."""
        new_state, entries = self._load(state)
        if new_state.status != model.SourceStateStatus.ERROR:
            assert self._source.interval is not None
            # next update is bigger of now + interval or expire (if set)
            next_update = datetime.datetime.now() + datetime.timedelta(
                seconds=common.parse_interval(self._source.interval)
            )
            new_state.next_update = max(
                new_state.next_update or next_update, next_update
            )

        return new_state, entries

    def _load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        url = self._conf["url"]
        headers = _prepare_headers(state)
        response = None
        try:
            response = requests.request(
                url=url,
                method="GET",
                headers=headers,
                timeout=self._conf["timeout"],
                allow_redirects=True,
            )

            if response is None:
                return state.new_error("no result"), []

            if response.status_code == 304:
                new_state = state.new_not_modified()
                if not new_state.icon:
                    new_state.set_icon(self._load_image(url))

                return new_state, []

            if response.status_code != 200:
                msg = f"Response code: {response.status_code}"
                if response.text:
                    msg += "\n" + response.text

                return state.new_error(msg), []

            url = self._check_redirects(response) or url

            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now()
            entry.status = (
                model.EntryStatus.UPDATED
                if state.last_update
                else model.EntryStatus.NEW
            )
            entry.title = self._source.name
            entry.url = url
            entry.content = response.text
            entry.set_opt("content-type", "html")

            new_state = state.new_ok(
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("last_modified"),
            )
            if not new_state.icon:
                new_state.set_icon(self._load_image(url))

            entry.icon = new_state.icon

            expires = common.parse_http_date(response.headers.get("expires"))
            if expires:
                new_state.next_update = expires
                new_state.set_state("expires", str(expires))

            return new_state, [entry]

        except requests.exceptions.RequestException as err:
            return state.new_error(f"request error: {err}"), []
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("WebInput error %s", err)
            return state.new_error(str(err)), []
        finally:
            if response:
                response.close()
                del response
                response = None

    def _check_redirects(
        self, response: requests.Response
    ) -> ty.Optional[str]:
        if not response.history:
            return None

        for hist in response.history:
            if hist.is_permanent_redirect:
                href = hist.headers.get("Location")
                if href:
                    self._update_source(new_url=href)
                    return href

        for hist in response.history:
            if hist.is_redirect:
                href = hist.headers.get("Location")
                if href:
                    self._update_source(new_url=href)
                    return href

        return None

    def _update_source(self, new_url: ty.Optional[str] = None) -> None:
        self._updated_source = self._updated_source or self._source.clone()
        if new_url:
            assert self._updated_source.settings is not None
            self._updated_source.settings["url"] = new_url

    def _load_image(
        self, url: str
    ) -> ty.Optional[ty.Tuple[str, bytes]]:  # pylint: disable=no-self-use
        url_splited = urlsplit(url)
        favicon_url = urlunsplit(
            (url_splited[0], url_splited[1], "favicon.ico", "", "")
        )
        if favicon_url:
            return self._load_binary(favicon_url)

        return None

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        assert source.settings is not None
        return {
            "text": source.name,
            "title": source.name,
            "type": "web",
            "xmlUrl": source.settings["url"],
            "htmlUrl": source.settings["url"],
        }

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        url = opml_node.get("htmlUrl") or opml_node["xmlUrl"]
        if not url:
            raise ValueError("missing xmlUrl")

        name = opml_node.get("text") or opml_node["title"]
        if not name:
            raise ValueError("missing text/title")

        src = model.Source(kind="rss", name=name, user_id=0, group_id=0)
        src.settings = {"url": url}
        return src


def _prepare_headers(state: model.SourceState) -> ty.Dict[str, str]:
    headers = {"User-agent": AbstractSource.AGENT, "Connection": "close"}
    if state.last_update:
        headers["If-Modified-Since"] = email.utils.formatdate(
            state.last_update.timestamp()
        )

    if state.state:
        etag = state.state.get("etag")
        if etag:
            headers["If-None-Match"] = etag

    return headers
