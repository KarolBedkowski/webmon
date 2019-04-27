#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Convert html to text.
"""
import typing as ty
import logging

import html2text as h2t

from webmon import common, model

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"
    params = [
        ("width", "Max line width", 999999, True, None, int),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any, ty.Any]]

    def validate(self):
        super().validate()
        width = self._conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid width: %r" % width)

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        conv = h2t.HTML2Text(bodywidth=self._conf.get("width"))
        conv.protect_links = True
        entry.content = conv.handle(entry.content)
        yield entry
