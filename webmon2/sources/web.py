# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Load data from webpage
"""

from __future__ import annotations

import datetime
import email.utils
import typing as ty
from urllib.parse import urlsplit, urlunsplit

import requests
from flask_babel import gettext, lazy_gettext
from lxml.html import clean

from webmon2 import common, model
from webmon2.filters.fix_urls import FixHtmlUrls

from .abstract import AbstractSource


class WebSource(AbstractSource):
    """Load data from web (http/https)"""

    name = "url"
    short_info = lazy_gettext("Web page")
    long_info = lazy_gettext("Load data form web page pointed by URL.")
    params = (
        common.SettingDef("url", lazy_gettext("Web page URL"), required=True),
        common.SettingDef(
            "timeout", lazy_gettext("Loading timeout"), default=30
        ),
        common.SettingDef(
            "fix_urls",
            lazy_gettext("Fix URL-s"),
            default=True,
        ),
        common.SettingDef(
            "http_headers",
            lazy_gettext("HTTP Headers"),
            default="",
            multiline=True,
        ),
    )

    def load(
        self, state: model.SourceState
    ) -> tuple[model.SourceState, model.Entries]:
        """Return one part - page content."""

        with requests.Session() as session:
            new_state, entries = self._load(state, session)

        if new_state.status != model.SourceStateStatus.ERROR:
            if self._conf["fix_urls"]:
                fltr = FixHtmlUrls({})
                entries = fltr.filter(entries, state, new_state)

            assert self._source.interval is not None
            # next update is bigger of now + interval or expire (if set)
            next_update = datetime.datetime.now(
                datetime.UTC
            ) + datetime.timedelta(
                seconds=common.parse_interval(self._source.interval)
            )
            new_state.next_update = max(
                new_state.next_update or next_update, next_update
            )

        return new_state, entries

    def _load_data(
        self, state: model.SourceState, session: requests.Session
    ) -> tuple[requests.Response, None] | tuple[None, model.SourceState]:
        url = self._conf["url"]
        headers = _prepare_headers(state, self._conf)
        response = session.request(
            url=url,
            method="GET",
            headers=headers,
            timeout=self._conf["timeout"],
            allow_redirects=True,
        )

        if response is None:
            return None, state.new_error("no result")

        if response.status_code == 304:  # noqa: PLR2004
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_image(url, session))

            return None, new_state

        if response.status_code != 200:  # noqa: PLR2004
            msg = gettext("Response code: %(code)s", code=response.status_code)
            if response.text:
                msg += "\n" + self._clean_content(response.text)

            return None, state.new_error(msg)

        return response, None

    def _load(
        self, state: model.SourceState, session: requests.Session
    ) -> tuple[model.SourceState, model.Entries]:
        url = self._conf["url"]
        self._log.debug("web source: load start")
        response = None
        try:
            response, new_state = self._load_data(state, session)
            if not response:
                # failed load data
                assert new_state
                return new_state, []

            new_state = state.new_ok(
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("last_modified"),
            )
            if not new_state.icon:
                new_state.set_icon(self._load_image(url, session))

            url = self._check_redirects(response, new_state) or url
            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now(datetime.UTC)
            entry.status = (
                model.EntryStatus.UPDATED
                if state.last_update
                else model.EntryStatus.NEW
            )
            entry.title = self._source.name
            entry.url = url
            entry.content = self._clean_content(response.text)
            entry.set_opt("content-type", "html")
            entry.icon = new_state.icon

            expires = common.parse_http_date(response.headers.get("expires"))
            if expires:
                new_state.next_update = expires
                new_state.set_prop("expires", str(expires))

        except requests.exceptions.RequestException as err:
            return state.new_error(f"request error: {err}"), []

        except Exception as err:  # pylint: disable=broad-except
            self._log.exception("web source: load error", error=err)
            return state.new_error(str(err)), []

        else:
            return new_state, [entry]

        finally:
            if response:
                response.close()
                del response
                response = None

    def _check_redirects(
        self, response: requests.Response, new_state: model.SourceState
    ) -> str | None:
        if not response.history:
            new_state.del_prop("info")
            return None

        for hist in response.history:
            if hist.is_permanent_redirect and (
                href := hist.headers.get("Location")
            ):
                new_state.set_prop(
                    "info",
                    gettext("Permanently redirects: %(url)s", url=href),
                )
                self._update_source(new_url=href)
                return href

        for hist in response.history:
            if hist.is_redirect and (href := hist.headers.get("Location")):
                self._update_source(new_url=href)
                new_state.set_prop(
                    "info",
                    gettext("Temporary redirects: %(url)s", url=href),
                )
                return href

        new_state.del_prop("info")
        return None

    def _update_source(self, new_url: str | None = None) -> None:
        self._updated_source = self._updated_source or self._source.clone()
        if new_url:
            assert self._updated_source.settings is not None
            self._updated_source.settings["url"] = new_url

    def _load_image(
        self, url: str, session: requests.Session
    ) -> tuple[str, bytes] | None:
        url_splited = urlsplit(url)
        favicon_url = urlunsplit(
            (
                url_splited[0],
                url_splited[1],
                "favicon.ico",
                "",
                "",
            )
        )
        if favicon_url:
            return self._load_binary(favicon_url, session=session)

        return None

    @classmethod
    def to_opml(
        cls: ty.Type[ty.Self], source: model.Source
    ) -> dict[str, ty.Any]:
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
        cls: ty.Type[ty.Self], opml_node: dict[str, ty.Any]
    ) -> model.Source | None:
        url = opml_node.get("htmlUrl") or opml_node["xmlUrl"]
        if not url:
            raise ValueError("missing xmlUrl")

        name = opml_node.get("text") or opml_node["title"]
        if not name:
            raise ValueError("missing text/title")

        src = model.Source(kind="rss", name=name, user_id=0, group_id=0)
        src.settings = {"url": url}
        return src

    def _clean_content(self, content: str) -> str:
        if not content:
            return content

        cleaner = clean.Cleaner(
            style=True,
            inline_style=False,
        )
        return ty.cast(str, clean.autolink_html(cleaner.clean_html(content)))


def _prepare_headers(
    state: model.SourceState, conf: model.ConfDict
) -> dict[str, str]:
    headers = {
        "User-agent": AbstractSource.AGENT,
    }

    headers.update(
        common.parse_str_to_headers(conf.get("default_http_headers"))
    )

    if state.last_update:
        headers["If-Modified-Since"] = email.utils.formatdate(
            state.last_update.timestamp()
        )

    if state.props and (etag := state.props.get("etag")):
        headers["If-None-Match"] = etag

    headers.update(common.parse_str_to_headers(conf.get("http_headers")))

    if not headers.get("Accept"):
        headers["Accept"] = (
            "text/html, application/xhtml+xml;q=0.9, text/plain, */*;q=0.8"
        )

    # if not already, set accept-language locale to user locale
    if not headers.get("Accept-Language"):
        # fallback value
        acc_lang = "en-US;q=0.7,en;q=0.3"
        if user_locale := conf.get("locale"):
            acc_lang = f"{user_locale},en-US;q=0.7,en;q=0.3"

        headers["Accept-Language"] = acc_lang

    return headers
