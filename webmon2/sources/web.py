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
from flask_babel import gettext, lazy_gettext
from lxml.html import clean

from webmon2 import common, model
from webmon2.filters.fix_urls import FixHtmlUrls

from .abstract import AbstractSource

_ = ty
_LOG = logging.getLogger(__name__)


class WebSource(AbstractSource):
    """Load data from web (http/https)"""

    name = "url"
    short_info = lazy_gettext("Web page")
    long_info = lazy_gettext("Load data form web page pointed by URL.")
    params = AbstractSource.params + [
        common.SettingDef("url", lazy_gettext("Web page URL"), required=True),
        common.SettingDef(
            "timeout", lazy_gettext("Loading timeout"), default=30
        ),
        common.SettingDef(
            "fix_urls",
            lazy_gettext("Fix URL-s"),
            default=True,
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
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
                datetime.timezone.utc
            ) + datetime.timedelta(
                seconds=common.parse_interval(self._source.interval)
            )
            new_state.next_update = max(
                new_state.next_update or next_update, next_update
            )

        return new_state, entries

    def _load(
        self, state: model.SourceState, session: requests.Session
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        url = self._conf["url"]
        headers = _prepare_headers(state)
        response = None
        try:
            response = session.request(
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
                    new_state.set_icon(self._load_image(url, session))

                return new_state, []

            if response.status_code != 200:
                msg = gettext(
                    "Response code: %(code)s", code=response.status_code
                )
                if response.text:
                    msg += "\n" + self._clean_content(response.text)

                return state.new_error(msg), []

            new_state = state.new_ok(
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("last_modified"),
            )
            if not new_state.icon:
                new_state.set_icon(self._load_image(url, session))

            url = self._check_redirects(response, new_state) or url
            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now(
                datetime.timezone.utc
            )
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
        self, response: requests.Response, new_state: model.SourceState
    ) -> ty.Optional[str]:
        if not response.history:
            new_state.del_prop("info")
            return None

        for hist in response.history:
            if hist.is_permanent_redirect:
                href = hist.headers.get("Location")
                if href:
                    new_state.set_prop(
                        "info",
                        gettext("Permanently redirects: %(url)s", url=href),
                    )
                    self._update_source(new_url=href)
                    return href

        for hist in response.history:
            if hist.is_redirect:
                href = hist.headers.get("Location")
                if href:
                    self._update_source(new_url=href)
                    new_state.set_prop(
                        "info",
                        gettext("Temporary redirects: %(url)s", url=href),
                    )
                    return href

        new_state.del_prop("info")
        return None

    def _update_source(self, new_url: ty.Optional[str] = None) -> None:
        self._updated_source = self._updated_source or self._source.clone()
        if new_url:
            assert self._updated_source.settings is not None
            self._updated_source.settings["url"] = new_url

    def _load_image(
        self, url: str, session: requests.Session
    ) -> ty.Optional[ty.Tuple[str, bytes]]:
        url_splited = urlsplit(url)
        favicon_url = urlunsplit(
            (url_splited[0], url_splited[1], "favicon.ico", "", "")
        )
        if favicon_url:
            return self._load_binary(favicon_url, session=session)

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

    def _clean_content(self, content: str) -> str:
        if not content:
            return content

        cleaner = clean.Cleaner(
            style=True,
            inline_style=False,
        )
        content = cleaner.clean_html(content)
        content = clean.autolink_html(content)
        return content


def _prepare_headers(state: model.SourceState) -> ty.Dict[str, str]:
    headers = {"User-agent": AbstractSource.AGENT, "Connection": "close"}
    if state.last_update:
        headers["If-Modified-Since"] = email.utils.formatdate(
            state.last_update.timestamp()
        )

    if state.props:
        etag = state.props.get("etag")
        if etag:
            headers["If-None-Match"] = etag

    return headers
