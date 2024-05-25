# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Jamendo input.
"""

from __future__ import annotations

import datetime

# import ssl
import time
import typing as ty
import urllib.parse

import requests
from flask_babel import gettext, lazy_gettext

from webmon2 import common, model

from .abstract import AbstractSource

if ty.TYPE_CHECKING:
    import structlog

# from urllib3 import poolmanager

JsonResult = list[dict[str, ty.Any]]

_JAMENDO_MAX_AGE = 90  # 90 days
_JAMENDO_ICON = (
    "https://cdn-www.jamendo.com/Client/assets/toolkit/images/"
    "icon/apple-touch-icon-180x180.1558632652000.png"
)


# pylint: disable=too-few-public-methods
class JamendoAbstractSource(AbstractSource):
    def __init__(
        self, source: model.Source, sys_settings: model.ConfDict
    ) -> None:
        super().__init__(source, sys_settings)
        self._update_source()

    def _get_last_update(self, state: model.SourceState) -> datetime.datetime:
        last_update = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=_JAMENDO_MAX_AGE
        )
        if state.last_update and state.last_update > last_update:
            last_update = state.last_update

        return last_update

    def _make_request_get_resp(
        self, response: requests.Response
    ) -> tuple[int, ty.Any]:
        if response.status_code == 304:  # noqa:PLR2004
            return 304, None

        if response.status_code != 200:  # noqa:PLR2004
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

    def _make_request(self, url: str) -> tuple[int, ty.Any]:
        self._log.debug("jamendo: make request", url=url)
        headers = {
            "User-agent": "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
            "Gecko/20100101 Firefox/45.0",
            "Connection": "close",
        }

        with requests.Session() as sess:
            response = None
            try:
                # sess.mount("https://", ForceTLSV1Adapter())
                response = sess.request(url=url, method="GET", headers=headers)
                response.raise_for_status()

                if not response:
                    return 500, "No response"

                return self._make_request_get_resp(response)

            except requests.exceptions.ReadTimeout:
                return 500, "timeout"
            except Exception as err:  # pylint: disable=broad-except
                return 500, str(err)
            finally:
                if response:
                    response.close()
                    del response
                    response = None

    def _update_source(self) -> None:
        """
        Make some updates in source settings (if necessary).
        """
        if not self._source.settings or self._source.settings.get("url"):
            return

        self._updated_source = self._updated_source or self._source.clone()
        self.__class__.upgrade_conf(self._updated_source)

    @classmethod
    def to_opml(
        cls: ty.Type[ty.Self], source: model.Source
    ) -> dict[str, ty.Any]:
        raise NotImplementedError

    @classmethod
    def from_opml(
        cls: ty.Type[ty.Self], opml_node: dict[str, ty.Any]
    ) -> model.Source | None:
        raise NotImplementedError

    @classmethod
    def upgrade_conf(
        cls: ty.Type[ty.Self], source: model.Source
    ) -> model.Source:
        """
        Update configuration before save; apply some additional data.
        """
        if source.settings:
            conf = source.settings
            conf["url"] = (
                f"https://www.jamendo.com/artist/{conf['artist_id']}/"
            )
        return source


def _build_request_url(url: str, **params: ty.Any) -> str:  # noqa: ANN401
    return url + "&".join(
        key + "=" + urllib.parse.quote_plus(str(val))
        for key, val in params.items()
        if val
    )


def _jamendo_track_to_url(track_id: int) -> str:
    return f"https://www.jamendo.com/track/{track_id}/" if track_id else ""


def _jamendo_album_to_url(album_id: int) -> str:
    return f"https://www.jamendo.com/album/{album_id}/" if album_id else ""


def _create_entry(
    source: model.Source, content: str, date: datetime.datetime
) -> model.Entry:
    entry = model.Entry.for_source(source)
    entry.title = source.name
    entry.status = model.EntryStatus.NEW
    entry.content = content
    entry.set_opt("content-type", "plain")
    entry.updated = entry.created = date
    return entry


class JamendoAlbumsSource(JamendoAbstractSource):
    """Load data from jamendo - new albums"""

    name = "jamendo_albums"
    short_info = lazy_gettext("Jamendo albums")
    long_info = lazy_gettext(
        "Check for new albums for given artist in Jamendo. "
        "Either artist ID or name must be configured; also source "
        "require configured 'Jamendo client ID'"
    )
    params = (
        common.SettingDef("artist_id", lazy_gettext("Artist ID")),
        common.SettingDef("artist", lazy_gettext("Artist name")),
        common.SettingDef(
            "jamendo_client_id",
            lazy_gettext("Jamendo client ID"),
            required=True,
            global_param=True,
        ),
    )

    def load(
        self, state: model.SourceState
    ) -> tuple[model.SourceState, list[model.Entry]]:
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

        self._log.debug("jamendo albums: load", url=url)

        status, res = self._make_request(url)
        if status == 304:  # noqa:PLR2004
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(_JAMENDO_ICON))
            return new_state, []
        if status != 200:  # noqa:PLR2004
            return state.new_error(res), []

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_JAMENDO_ICON))

        entries = list(
            _jamendo_format_long_list(self._source, res["results"], self._log)
        )
        for entry in entries:
            entry.icon = new_state.icon

        self._log.debug("jamendo albums: load done")
        return new_state, entries

    @classmethod
    def validate_conf(
        cls: ty.Type[ty.Self], *confs: model.ConfDict
    ) -> ty.Iterable[tuple[str, str]]:
        """Validate input configuration."""
        yield from super().validate_conf(*confs)
        artist_id = any(conf.get("artist_id") for conf in confs)
        artist = any(conf.get("artist") for conf in confs)
        if not artist_id and not artist:
            yield ("artist_id", "artist name or id is required")

    @classmethod
    def to_opml(
        cls: ty.Type[ty.Self], source: model.Source
    ) -> dict[str, ty.Any]:
        raise NotImplementedError

    @classmethod
    def from_opml(
        cls: ty.Type[ty.Self], opml_node: dict[str, ty.Any]
    ) -> model.Source | None:
        raise NotImplementedError


def _jamendo_format_long_list(
    source: model.Source,
    results: JsonResult,
    log: structlog.stdlib.BoundLogger,
) -> model.Entries:
    for result in results:
        for album in result.get("albums") or []:
            yield _create_entry(
                source,
                f'{album["releasedate"]} {album["name"]} '
                f'{_jamendo_album_to_url(album["id"])}',
                _get_release_date(album, log),
            )


class JamendoTracksSource(JamendoAbstractSource):
    """Load data from jamendo - new tracks for artists"""

    name = "jamendo_tracks"
    short_info = lazy_gettext("Jamendo tracks")
    long_info = lazy_gettext(
        "Check for new tracks for given artist in Jamendo. "
        "Either artist ID or name must be configured; also source "
        "require configured 'Jamendo client ID'"
    )
    params = (
        common.SettingDef("artist_id", lazy_gettext("Artist ID")),
        common.SettingDef("artist", lazy_gettext("Artist name")),
        common.SettingDef(
            "jamendo_client_id",
            lazy_gettext("Jamendo client ID"),
            required=True,
            global_param=True,
        ),
    )

    def load(
        self, state: model.SourceState
    ) -> tuple[model.SourceState, list[model.Entry]]:
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
        if status == 304:  # noqa:PLR2004
            new_state = state.new_not_modified()
            if not new_state.icon:
                new_state.set_icon(self._load_binary(_JAMENDO_ICON))

            return new_state, []

        if status != 200:  # noqa:PLR2004
            return state.new_error(res), []

        new_state = state.new_ok()
        if not new_state.icon:
            new_state.set_icon(self._load_binary(_JAMENDO_ICON))

        entries = list(
            _jamendo_track_format(self._source, res["results"], self._log)
        )
        for entry in entries:
            entry.icon = new_state.icon

        self._log.debug("jamendo tracks: load done")
        return new_state, entries

    @classmethod
    def validate_conf(
        cls: ty.Type[ty.Self], *confs: model.ConfDict
    ) -> ty.Iterable[tuple[str, str]]:
        """Validate input configuration."""
        yield from super().validate_conf(*confs)
        artist_id = any(conf.get("artist_id") for conf in confs)
        artist = any(conf.get("artist") for conf in confs)
        if not artist_id and not artist:
            yield ("artist_id", gettext("artist name or id is required"))

    @classmethod
    def to_opml(
        cls: ty.Type[ty.Self], source: model.Source
    ) -> dict[str, ty.Any]:
        raise NotImplementedError

    @classmethod
    def from_opml(
        cls: ty.Type[ty.Self], opml_node: dict[str, ty.Any]
    ) -> model.Source | None:
        raise NotImplementedError


def _track_to_content_line(track: dict[str, ty.Any]) -> str:
    return (
        f"{track['releasedate']} {track['name']} "
        f"{_jamendo_track_to_url(track['id'])}"
    )


def _jamendo_track_format(
    source: model.Source,
    results: JsonResult,
    log: structlog.stdlib.BoundLogger,
) -> model.Entries:
    for result in results:
        if tracks := result.get("tracks"):
            yield _create_entry(
                source,
                "\n".join(map(_track_to_content_line, tracks)),
                max(_get_release_date(trc, log) for trc in tracks),
            )


def _get_release_date(
    data: dict[str, str], log: structlog.stdlib.BoundLogger
) -> datetime.datetime:
    try:
        releasedate = datetime.datetime.fromisoformat(data["releasedate"])
        if not releasedate.tzinfo:
            releasedate = releasedate.replace(tzinfo=datetime.UTC)

    except ValueError:
        log.debug("jamendo: wrong releasedate", data=data)
        return datetime.datetime.now(datetime.UTC)

    except KeyError:
        log.debug("jamendo: missing releasedate", data=data)
        return datetime.datetime.now(datetime.UTC)

    else:
        return releasedate


# class ForceTLSV1Adapter(requests.adapters.HTTPAdapter):
#     """Require TLSv1 for the connection"""

#     def init_poolmanager(self, connections, maxsize, block=False, **_kwargs):
#         self.poolmanager = poolmanager.PoolManager(
#             num_pools=connections,
#             maxsize=maxsize,
#             block=block,
#             ssl_version=ssl.PROTOCOL_TLSv1,
#         )
