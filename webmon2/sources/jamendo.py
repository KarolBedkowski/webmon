#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Jamendo input.
"""
import datetime
import logging

# import ssl
import time
import typing as ty
import urllib.parse

import requests

# from urllib3 import poolmanager

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)
_JAMENDO_MAX_AGE = 90  # 90 days
_JAMENDO_ICON = (
    "https://cdn-www.jamendo.com/Client/assets/toolkit/images/"
    "icon/apple-touch-icon-180x180.1558632652000.png"
)


# pylint: disable=too-few-public-methods
class JamendoMixin:
    def _get_last_update(self, state):  # pylint: disable=no-self-use
        last_update = datetime.datetime.now() - datetime.timedelta(
            days=_JAMENDO_MAX_AGE
        )
        if state.last_update and state.last_update > last_update:
            last_update = state.last_update

        return last_update

    # pylint: disable=no-self-use,too-many-return-statements
    def _make_request(self, url):
        _LOG.debug("make request: %s", url)
        headers = {
            "User-agent": "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
            "Gecko/20100101 Firefox/45.0"
        }
        with requests.Session() as sess:
            try:
                # sess.mount("https://", ForceTLSV1Adapter())
                response = sess.request(url=url, method="GET", headers=headers)
                response.raise_for_status()
            except requests.exceptions.ReadTimeout:
                return 500, "timeout"
            except Exception as err:  # pylint: disable=broad-except
                return 500, str(err)

            if response.status_code == 304:
                return 304, None

            if response.status_code != 200:
                msg = f"Response code: {response.status_code}"
                if response.text:
                    msg += "\n" + response.text
                return 500, msg

            res = response.json()
            try:
                if res["headers"]["status"] != "success":
                    return 500, res["headers"]["error_message"]
            except KeyError:
                return 500, "wrong answer"

            if not res["results"]:
                return 304, None

            return 200, res


def _build_request_url(url, **params):
    return url + "&".join(
        key + "=" + urllib.parse.quote_plus(str(val))
        for key, val in params.items()
        if val
    )


def _jamendo_track_to_url(track_id) -> str:
    if not track_id:
        return ""
    return f"https://www.jamendo.com/track/{track_id}/"


def _jamendo_album_to_url(album_id):
    if not album_id:
        return ""
    return f"https://www.jamendo.com/album/{album_id}/"


def _create_entry(source: model.Source, content: str, date) -> model.Entry:
    entry = model.Entry.for_source(source)
    entry.title = source.name
    entry.status = "new"
    entry.content = content
    entry.set_opt("content-type", "plain")
    entry.updated = entry.created = date
    return entry


class JamendoAlbumsSource(AbstractSource, JamendoMixin):
    """Load data from jamendo - new albums"""

    name = "jamendo_albums"
    short_info = "Jamendo albums"
    long_info = (
        "Check for new albums for given artist in Jamendo. "
        "Either artist is or name must be configured; also source "
        'require configured "jamendo client id"'
    )
    params = AbstractSource.params + [
        common.SettingDef("artist_id", "artist id"),
        common.SettingDef("artist", "artist name"),
        common.SettingDef(
            "jamendo_client_id",
            "jamendo client id",
            required=True,
            global_param=True,
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return one part - page content."""
        conf = self._conf
        last_update = self._get_last_update(state)
        url = _build_request_url(
            "https://api.jamendo.com/v3.0/artists/albums?",
            client_id=conf["jamendo_client_id"],
            format="json",
            order="album_releasedate_desc",
            name=conf.get("artist"),
            id=conf.get("artist_id"),
            album_datebetween=last_update.strftime("%Y-%m-%d")
            + "_"
            + time.strftime("%Y-%m-%d"),
        )

        _LOG.debug("load url=%s", url)

        status, res = self._make_request(url)
        if status == 304:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(_JAMENDO_ICON))
            return new_state, []
        if status != 200:
            return state.new_error(res), []

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_JAMENDO_ICON))

        entries = list(_jamendo_format_long_list(self._source, res["results"]))
        for entry in entries:
            entry.icon = new_state.icon

        _LOG.debug("JamendoAlbumsSource: load done")
        return new_state, entries

    @classmethod
    def validate_conf(cls, *confs) -> ty.Iterable[ty.Tuple[str, str]]:
        """Validate input configuration."""
        yield from super(JamendoAlbumsSource, cls).validate_conf(*confs)
        artist_id = any(conf.get("artist_id") for conf in confs)
        artist = any(conf.get("artist") for conf in confs)
        if not artist_id and not artist:
            yield ("artist_id", "artist name or id is required")

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


def _jamendo_format_long_list(source: model.Source, results) -> model.Entries:
    for result in results:
        for album in result.get("albums") or []:
            yield _create_entry(
                source,
                " ".join(
                    (
                        album["releasedate"],
                        album["name"],
                        _jamendo_album_to_url(album["id"]),
                    )
                ),
                _get_release_date(album),
            )


class JamendoTracksSource(AbstractSource, JamendoMixin):
    """Load data from jamendo - new tracks for artists"""

    name = "jamendo_tracks"
    short_info = "Jamendo tracks"
    long_info = (
        "Check for new tracks for given artist in Jamendo. "
        "Either artist is or name must be configured; also source "
        'require configured "jamendo client id"'
    )
    params = AbstractSource.params + [
        common.SettingDef("artist_id", "artist id"),
        common.SettingDef("artist", "artist name"),
        common.SettingDef(
            "jamendo_client_id",
            "jamendo client id",
            required=True,
            global_param=True,
        ),
    ]  # type: ty.List[common.SettingDef]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return one part - page content."""
        conf = self._conf
        last_update = self._get_last_update(state)
        url = _build_request_url(
            "https://api.jamendo.com/v3.0/artists/tracks?",
            client_id=conf["jamendo_client_id"],
            format="json",
            order="track_releasedate_desc",
            name=conf.get("artist"),
            id=conf.get("artist_id"),
            album_datebetween=last_update.strftime("%Y-%m-%d")
            + "_"
            + time.strftime("%Y-%m-%d"),
        )

        status, res = self._make_request(url)
        if status == 304:
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(_JAMENDO_ICON))
            return new_state, []
        if status != 200:
            return state.new_error(res), []

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_JAMENDO_ICON))

        entries = list(_jamendo_track_format(self._source, res["results"]))
        for entry in entries:
            entry.icon = new_state.icon

        _LOG.debug("JamendoTracksSource: load done")
        return new_state, entries

    @classmethod
    def validate_conf(cls, *confs) -> ty.Iterable[ty.Tuple[str, str]]:
        """Validate input configuration."""
        yield from super(JamendoTracksSource, cls).validate_conf(*confs)
        artist_id = any(conf.get("artist_id") for conf in confs)
        artist = any(conf.get("artist") for conf in confs)
        if not artist_id and not artist:
            yield ("artist_id", "artist name or id is required")

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


def _jamendo_track_format(source: model.Source, results) -> model.Entries:
    for result in results:
        tracks = result.get("tracks")
        if tracks:
            yield _create_entry(
                source,
                "\n".join(
                    " ".join(
                        (
                            track["releasedate"],
                            track["name"],
                            _jamendo_track_to_url(track["id"]),
                        )
                    )
                    for track in tracks
                ),
                max(_get_release_date(trc) for trc in tracks),
            )


def _get_release_date(data) -> datetime.datetime:
    try:
        return datetime.datetime.fromisoformat(data["releasedate"])
    except ValueError:
        _LOG.debug("wrong releasedate in %s", data)
        return datetime.datetime.now()
    except KeyError:
        _LOG.debug("missing releasedate in %s", data)
        return datetime.datetime.now()


# class ForceTLSV1Adapter(requests.adapters.HTTPAdapter):
#     """Require TLSv1 for the connection"""

#     def init_poolmanager(self, connections, maxsize, block=False, **_kwargs):
#         self.poolmanager = poolmanager.PoolManager(
#             num_pools=connections,
#             maxsize=maxsize,
#             block=block,
#             ssl_version=ssl.PROTOCOL_TLSv1,
#         )
