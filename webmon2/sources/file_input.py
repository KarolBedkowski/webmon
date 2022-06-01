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
        'Source check local, text file defined by "Full file patch" setting'
    )
    params = AbstractSource.params + [
        common.SettingDef("filename", "Full file patch", required=True),
    ]

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
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
            with open(fname, "r", encoding="UTF-8") as finput:
                content = finput.read()

            _LOG.debug(
                "load content source=%d, content=%s", self._source.id, content
            )

            entry = model.Entry.for_source(self._source)
            entry.updated = entry.created = datetime.datetime.utcnow()
            entry.status = (
                model.EntryStatus.UPDATED
                if state.last_update
                else model.EntryStatus.NEW
            )
            entry.title = self._source.name
            entry.url = fname
            entry.content = content
            entry.set_opt("content-type", "plain")
            new_state = state.new_ok()
            assert self._source.interval is not None
            new_state.next_update = (
                datetime.datetime.utcnow()
                + datetime.timedelta(
                    seconds=common.parse_interval(self._source.interval)
                )
            )
            return new_state, [entry]
        except IOError as err:
            return state.new_error(str(err)), []

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        assert source.settings is not None
        return {
            "text": source.name,
            "title": source.name,
            "type": cls.name,
            "xmlUrl": "file://" + source.settings["filename"],
            "htmlUrl": "file://" + source.settings["filename"],
        }

    @classmethod
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        url = opml_node.get("htmlUrl") or opml_node["xmlUrl"]
        if not url or not url.startswith("file://"):
            raise ValueError("missing xmlUrl")

        name = opml_node.get("text") or opml_node["title"]
        if not name:
            raise ValueError("missing text/title")

        filename = url[7:]
        src = model.Source(
            user_id=0,
            group_id=0,
            kind=cls.name,
            name=name,
        )
        src.settings = {"filename": filename}
        return src
