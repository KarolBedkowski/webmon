#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""

"""
import typing as ty

from webmon import common, model

from ._abstract import AbstractFilter

_ = ty


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "html2text"
    params = [
        ("width", "Max line width", 999999, True, None),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any]]

    def validate(self):
        super().validate()
        width = self._conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid width: %r" % width)

    def _filter(self, entry: model.Entry) -> model.Entries:
        if not entry.content:
            return
        try:
            import html2text as h2t
        except ImportError:
            raise common.FilterError(self, "module html2text not found")

        conv = h2t.HTML2Text(bodywidth=self._conf.get("width"))
        entry.content = conv.handle(entry.content.decode('utf-8'))
        yield entry
