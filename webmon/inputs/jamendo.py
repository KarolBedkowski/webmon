#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
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

from webmon import common, model

from .abstract import AbstractInput


_LOG = logging.getLogger(__file__)
_JAMENDO_MAX_AGE = 90  # 90 days


class JamendoAlbumsInput(AbstractInput):
    """Load data from jamendo - new albums"""

    name = "jamendo_albums"
    params = AbstractInput.params + [
        ("artist_id", "artist id", None, False, None, str),
        ("artist", "artist name", None, False, None, str),
        ("jamendo_client_id", "jamendo client id", None, True, None, str),
        ("short_list", "show compact list", True, False, None, str),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def load(self, state: model.SourceState) -> \
            (model.SourceState, [model.Entry]):
        """ Return one part - page content. """
        conf = self._conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if not (conf.get("artist_id") or conf.get("artist")):
            raise common.ParamError(
                "missing parameter 'artist' or 'artist_id'")

        last_updated = datetime.datetime.now() - \
            datetime.timedelta(days=_JAMENDO_MAX_AGE)
        if state.last_update and state.last_updated > last_updated:
            last_updated = state.last_updated

        url = _jamendo_build_service_url(conf, last_updated)
        _LOG.debug("JamendoAlbumsInput: loading url: %s", url)
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
        _LOG.debug("JamendoAlbumsInput: load done")
        new_state = state.new_ok()
        return new_state, result


def _jamendo_build_service_url(conf: ty.Dict[str, ty.Any],
                               last_updated: datetime.datetime) -> str:
    last_updated = last_updated.strftime("%Y-%m-%d")
    today = time.strftime("%Y-%m-%d")
    artist = (("name=" + conf["artist"]) if conf.get('artist')
              else ("id=" + str(conf["artist_id"])))
    url = 'https://api.jamendo.com/v3.0/artists/albums?'
    url += '&'.join(("client_id=" + conf.get('jamendo_client_id', ''),
                     "format=json&order=album_releasedate_desc",
                     artist,
                     "album_datebetween=" + last_updated + "_" + today))
    return url


def _jamendo_album_to_url(album_id):
    if not album_id:
        return ''
    return 'https://www.jamendo.com/album/{}/'.format(album_id)


def _jamendo_format_short_list(source, results):
    for result in results:
        entry = model.Entry.for_source(source)
        entry.title = source.title
        entry.content = "\n".join(
            " ".join((album['releasedate'], album["name"],
                      _jamendo_album_to_url(album['id'])))
            for album in result.get('albums') or [])
        yield entry


def _jamendo_format_long_list(source, results):
    for result in results:
        for album in result.get('albums') or []:
            entry = model.Entry.for_source(source)
            entry.title = source.title
            entry.content = " ".join(
                (album['releasedate'], album["name"],
                 _jamendo_album_to_url(album['id'])))
            yield entry


class JamendoTracksInput(AbstractInput):
    """Load data from jamendo - new tracks for artists"""

    name = "jamendo_tracks"
    params = AbstractInput.params + [
        ("artist_id", "artist id", None, False, None, str),
        ("artist", "artist name", None, False, None, str),
        ("jamendo_client_id", "jamendo client id", None, True, None, str),
        ("short_list", "show compact list", True, False, None, str),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def load(self, state: model.SourceState) -> \
            (model.SourceState, [model.Entry]):
        """ Return one part - page content. """
        conf = self._conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if not (conf.get("artist_id") or conf.get("artist")):
            raise common.ParamError(
                "missing parameter 'artist' or 'artist_id'")

        last_updated = datetime.datetime.now() - \
            datetime.timedelta(days=_JAMENDO_MAX_AGE)
        if state.last_update and state.last_updated > last_updated:
            last_updated = state.last_updated

        url = _jamendo_build_url_tracks(conf, last_updated)

        _LOG.debug("JamendoTracksInput: loading url: %s", url)
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
        return new_state, entries


def _jamendo_build_url_tracks(conf, last_updated):
    last_updated = last_updated.strftime("%Y-%m-%d")
    today = time.strftime("%Y-%m-%d")
    artist = (("name=" + conf["artist"]) if conf.get('artist')
              else ("id=" + str(conf["artist_id"])))
    url = 'https://api.jamendo.com/v3.0/artists/tracks?'
    url += '&'.join(("client_id=" + conf.get('jamendo_client_id', ''),
                     "format=json&order=track_releasedate_desc",
                     artist,
                     "album_datebetween=" + last_updated + "_" + today))
    return url


def _jamendo_track_to_url(track_id):
    if not track_id:
        return ''
    return 'https://www.jamendo.com/track/{}/'.format(track_id)


def _jamendo_track_format_short(source, results):
    for result in results:
        entry = model.Entry.for_source(source)
        entry.title = source.title
        entry.content = "\n".join(
            " ".join((track['releasedate'], track["name"],
                      _jamendo_track_to_url(track['id'])))
            for track in result.get('tracks') or [])
        yield entry


def _jamendo_track_format_long(source, results):
    for result in results:
        for track in result.get('tracks') or []:
            res_track = [track['releasedate'], track["name"],
                         _jamendo_track_to_url(track['id'])]
            album = track.get('album_id')
            if album:
                res_track.append(" (" + track['album_name'] +
                                 _jamendo_album_to_url(track['album_id']))

            entry = model.Entry.for_source(source)
            entry.title = source.title
            entry.content = " ".join(res_track)
            yield entry


class ForceTLSV1Adapter(requests.adapters.HTTPAdapter):
    """Require TLSv1 for the connection"""

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_version=ssl.PROTOCOL_TLSv1,
        )
