#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""

"""
import email.utils
import datetime
import logging
import typing as ty

import requests

from webmon import common, model

from .abstract import AbstractInput


_ = ty
_LOG = logging.getLogger(__file__)


class WebInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "url"
    params = AbstractInput.params + [
        ("url", "Web page url", None, True, None, str),
        ("timeout", "loading timeout", 30, True, None, int),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def load(self, state: model.SourceState) -> \
            (model.SourceState, [model.Entry]):
        """ Return one part - page content.
        """
        new_state, entries = self._load(state)
        if new_state.status != 'error':
            new_state.next_update = datetime.datetime.now() + \
                datetime.timedelta(
                    minutes=common.parse_interval(self._source.interval))
        return new_state, entries

    def _load(self, state: model.SourceState):
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if state.last_update:
            headers['If-Modified-Since'] = email.utils.formatdate(
                state.last_update.timestamp())
        url = self._conf['url']
        response = None
        try:
            response = requests.request(url=url, method='GET',
                                        headers=headers,
                                        timeout=self._conf['timeout'],
                                        allow_redirects=True)
            if not response:
                return state.new_error("no result"), []

            response.raise_for_status()

            if response.status_code == 304:
                return state.new_not_modified(), []

            if response.status_code != 200:
                msg = "Response code: %d" % response.status_code
                if response.text:
                    msg += "\n" + response.text
                return state.new_error(msg), []

            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now()
            entry.status = 'updated' if state.last_update else 'new'
            entry.title = self._source.name
            entry.url = url
            entry.content = response.text
            new_state = state.new_ok()
            return new_state, [entry]
        except requests.exceptions.ReadTimeout:
            return state.new_error("timeout"), []
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("WebInput error %s", err)
            return state.new_error(str(err)), []
        finally:
            if response:
                response.close()
