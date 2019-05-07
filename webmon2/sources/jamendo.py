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
import json
import ssl
import time
import datetime
import typing as ty
import logging

import requests
from urllib3 import poolmanager

from webmon2 import common, model

from .abstract import AbstractSource


_LOG = logging.getLogger(__file__)
_JAMENDO_MAX_AGE = 90  # 90 days


class JamendoAlbumsSource(AbstractSource):
    """Load data from jamendo - new albums"""

    name = "jamendo_albums"
    short_info = "Jamendo albums"
    long_info = 'Check for new albums for given artist in Jamendo. ' \
        'Either artist is or name must be configured; also source ' \
        'require configured "jamendo client id"'
    params = AbstractSource.params + [
        common.SettingDef("artist_id", "artist id"),
        common.SettingDef("artist", "artist name"),
        common.SettingDef("jamendo_client_id", "jamendo client id",
                          required=True, global_param=True),
        common.SettingDef("short_list", "show compact list", default=True),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) -> \
            ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """ Return one part - page content. """
        conf = self._conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if not (conf.get("artist_id") or conf.get("artist")):
            raise common.ParamError(
                "missing parameter 'artist' or 'artist_id'")

        last_update = datetime.datetime.now() - \
            datetime.timedelta(days=_JAMENDO_MAX_AGE)
        if state.last_update and state.last_update > last_update:
            last_update = state.last_update

        url = _jamendo_build_service_url(conf, last_update)
        _LOG.debug("JamendoAlbumsSource: loading url: %s", url)
        try:
            sess = requests.Session()
            sess.mount("https://", ForceTLSV1Adapter())
            response = sess.request(url=url, method='GET', headers=headers)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            return state.new_error("timeout"), []
        except Exception as err:  # pylint: disable=broad-except
            return state.new_error(str(err)), []

        if response.status_code == 304:
            response.close()
            return state.new_not_modified(), []

        if response.status_code != 200:
            msg = "Response code: %d" % response.status_code
            if response.text:
                msg += "\n" + response.text
            response.close()
            return state.new_error(msg), []

        res = json.loads(response.text)
        if res['headers']['status'] != 'success':
            response.close()
            return state.new_error(res['headers']['error_message']), []

        if conf.get('short_list'):
            result = _jamendo_format_short_list(self._source, res['results'])
        else:
            result = _jamendo_format_long_list(self._source, res['results'])

        response.close()
        _LOG.debug("JamendoAlbumsSource: load done")
        new_state = state.new_ok()
        return new_state, list(result)

    @classmethod
    def validate_conf(cls, *confs) -> ty.Iterable[ty.Tuple[str, str]]:
        """ Validate input configuration."""
        yield from super(JamendoAlbumsSource, cls).validate_conf(*confs)
        artist_id = [conf['artist_id'] for conf in confs
                     if conf.get('artist_id')]
        artist = [conf['artist'] for conf in confs if conf.get('artist')]
        if not artist_id and not artist:
            yield ('artist_id', "artist name or id is required")


def _jamendo_build_service_url(conf: ty.Dict[str, ty.Any],
                               last_update: datetime.datetime) -> str:
    last_update_str = last_update.strftime("%Y-%m-%d")
    today = time.strftime("%Y-%m-%d")
    artist = (("name=" + conf["artist"]) if conf.get('artist')
              else ("id=" + str(conf["artist_id"])))
    url = 'https://api.jamendo.com/v3.0/artists/albums?'
    url += '&'.join(("client_id=" + conf.get('jamendo_client_id', ''),
                     "format=json&order=album_releasedate_desc",
                     artist,
                     "album_datebetween=" + last_update_str + "_" + today))
    return url


def _jamendo_album_to_url(album_id):
    if not album_id:
        return ''
    return 'https://www.jamendo.com/album/{}/'.format(album_id)


def _jamendo_format_short_list(source: model.Source, results) -> model.Entries:
    for result in results:
        entry = model.Entry.for_source(source)
        entry.title = source.name
        entry.content = "\n".join(
            " ".join((album['releasedate'], album["name"],
                      _jamendo_album_to_url(album['id'])))
            for album in result.get('albums') or [])
        entry.set_opt("content-type", "html")
        entry.updated = entry.created = _get_release_date_from_list(
            result.get('albums'))
        yield entry


def _jamendo_format_long_list(source: model.Source, results) -> model.Entries:
    for result in results:
        for album in result.get('albums') or []:
            entry = model.Entry.for_source(source)
            entry.title = source.name
            entry.content = " ".join(
                (album['releasedate'], album["name"],
                 _jamendo_album_to_url(album['id'])))
            entry.set_opt("content-type", "plain")
            entry.updated = entry.created = _get_release_date(result)
            yield entry


class JamendoTracksSource(AbstractSource):
    """Load data from jamendo - new tracks for artists"""

    name = "jamendo_tracks"
    short_info = "Jamendo tracks"
    long_info = 'Check for new tracks for given artist in Jamendo. ' \
        'Either artist is or name must be configured; also source ' \
        'require configured "jamendo client id"'
    params = AbstractSource.params + [
        common.SettingDef("artist_id", "artist id"),
        common.SettingDef("artist", "artist name"),
        common.SettingDef("jamendo_client_id", "jamendo client id",
                          required=True, global_param=True),
        common.SettingDef("short_list", "show compact list", default=True),
    ]  # type: ty.List[common.SettingDef]

    def load(self, state: model.SourceState) -> \
            ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """ Return one part - page content. """
        conf = self._conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if not (conf.get("artist_id") or conf.get("artist")):
            raise common.ParamError(
                "missing parameter 'artist' or 'artist_id'")

        last_update = datetime.datetime.now() - \
            datetime.timedelta(days=_JAMENDO_MAX_AGE)
        if state.last_update and state.last_update > last_update:
            last_update = state.last_update

        url = _jamendo_build_url_tracks(conf, last_update)

        _LOG.debug("JamendoTracksSource: loading url: %s", url)
        try:
            sess = requests.Session()
            sess.mount("https://", ForceTLSV1Adapter())
            response = sess.request(url=url, method='GET', headers=headers)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            return state.new_error("timeout"), []
        except Exception as err:  # pylint: disable=broad-except
            return state.new_error(str(err)), []

        if response.status_code == 304:
            response.close()
            return state.new_not_modified(), []

        if response.status_code != 200:
            msg = "Response code: %d" % response.status_code
            if response.text:
                msg += "\n" + response.text
            response.close()
            return state.new_error(msg), []

        res = json.loads(response.text)

        if res['headers']['status'] != 'success':
            response.close()
            return state.new_error(res['headers']['error_message']), []

        if conf.get('short_list'):
            entries = _jamendo_track_format_short(self._source, res['results'])
        else:
            entries = _jamendo_track_format_long(self._source, res['results'])

        response.close()
        new_state = state.new_ok()
        return new_state, list(entries)

    @classmethod
    def validate_conf(cls, *confs) -> ty.Iterable[ty.Tuple[str, str]]:
        """ Validate input configuration."""
        yield from super(JamendoTracksSource, cls).validate_conf(*confs)
        artist_id = [conf['artist_id'] for conf in confs
                     if conf.get('artist_id')]
        artist = [conf['artist'] for conf in confs if conf.get('artist')]
        if not artist_id and not artist:
            yield ('artist_id', "artist name or id is required")


def _jamendo_build_url_tracks(conf, last_update) -> str:
    last_update = last_update.strftime("%Y-%m-%d")
    today = time.strftime("%Y-%m-%d")
    artist = (("name=" + conf["artist"]) if conf.get('artist')
              else ("id=" + str(conf["artist_id"])))
    url = 'https://api.jamendo.com/v3.0/artists/tracks?'
    url += '&'.join(("client_id=" + conf.get('jamendo_client_id', ''),
                     "format=json&order=track_releasedate_desc",
                     artist,
                     "album_datebetween=" + last_update + "_" + today))
    return url


def _jamendo_track_to_url(track_id) -> str:
    if not track_id:
        return ''
    return 'https://www.jamendo.com/track/{}/'.format(track_id)


def _jamendo_track_format_short(source: model.Source, results) \
        -> model.Entries:
    for result in results:
        entry = model.Entry.for_source(source)
        entry.title = source.name
        entry.content = "\n".join(
            " ".join((track['releasedate'], track["name"],
                      _jamendo_track_to_url(track['id'])))
            for track in result.get('tracks') or [])
        entry.set_opt("content-type", "plain")
        entry.updated = entry.created = _get_release_date_from_list(
            result.get('tracks'))
        yield entry


def _jamendo_track_format_long(source: model.Source, results) -> model.Entries:
    for result in results:
        for track in result.get('tracks') or []:
            res_track = [track['releasedate'], track["name"],
                         _jamendo_track_to_url(track['id'])]
            album = track.get('album_id')
            if album:
                res_track.append(" (" + track['album_name'] +
                                 _jamendo_album_to_url(track['album_id']))

            entry = model.Entry.for_source(source)
            entry.title = source.name
            entry.content = " ".join(res_track)
            entry.updated = entry.created = _get_release_date(track)
            entry.set_opt("content-type", "plain")
            yield entry


def _get_release_date(data) -> datetime.date:
    try:
        return datetime.datetime.fromisoformat(data['releasedate'])
    except ValueError:
        _LOG.debug("wrong releasedate in %s", data)
        return datetime.date.today()
    except KeyError:
        _LOG.debug("missing releasedate in %s", data)
        return datetime.date.today()


def _get_release_date_from_list(content) -> datetime.date:
    return max(_get_release_date(entry) for entry in content)


class ForceTLSV1Adapter(requests.adapters.HTTPAdapter):
    """Require TLSv1 for the connection"""

    def init_poolmanager(self, connections, maxsize, block=False, **_kwargs):
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLSv1,
        )
