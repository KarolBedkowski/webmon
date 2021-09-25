#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Local file source
"""
import datetime
import logging
import os
import typing as ty

from webmon2 import common, model

from .abstract import AbstractSource

_LOG = logging.getLogger(__name__)


class FileSource(AbstractSource):
    """Load data from local file"""

    name = "file"
    short_info = "Data from local file"
    long_info = (
        'Source check local, text file defined by "Full file patch"' " setting"
    )
    params = AbstractSource.params + [
        common.SettingDef("filename", "Full file patch", required=True),
    ]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """Return one part - page content."""

        fname = self._conf["filename"]
        _LOG.debug("load start source=%d, file=%s", self._source.id, fname)

        if not os.path.isfile(fname):
            return state.new_error("no file"), []

        if state.last_update:
            fid = os.open(fname, os.O_RDONLY)
            stat = os.fstat(fid)
            file_change = stat.st_mtime
            os.close(fid)

            if file_change <= state.last_update.timestamp():
                return state.new_not_modified(), []

        try:
            content = ""
            with open(fname, "r") as finput:
                content = finput.read()

            _LOG.debug(
                "load content source=%d, content=%s", self._source.id, content
            )

            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.now()
            entry.status = "updated" if state.last_update else "new"
            entry.title = self._source.name
            entry.url = fname
            entry.content = content
            entry.set_opt("content-type", "plain")
            new_state = state.new_ok()
            new_state.status = "updated" if state.last_update else "new"
            new_state.next_update = (
                datetime.datetime.now()
                + datetime.timedelta(
                    seconds=common.parse_interval(self._source.interval)
                )
            )
            return new_state, [entry]
        except IOError as err:
            return state.new_error(str(err)), []
