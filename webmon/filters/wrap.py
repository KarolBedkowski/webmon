#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Wrap entry content lines
"""
import typing as ty
import textwrap

from webmon import common, model

from ._abstract import AbstractFilter

_ = ty


class Html2Text(AbstractFilter):
    """Convert html to text using html2text module."""

    name = "wrap"
    params = [
        ("width", "Max line width", 76, True, None),
        ("max_lines", "Max number of lines", None, False, None),
    ]  # type: ty.List[ty.Tuple[str, str, ty.Any, bool, ty.Any]]

    def validate(self):
        super().validate()
        width = self._conf.get("width")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid width: %r" % width)
        max_lines = self._conf.get("max_lines")
        if not isinstance(width, int) or width < 1:
            raise common.ParamError("invalid max_lines: %r" % max_lines)

    def _filter(self, entry: model.Entry) -> model.Entries:
        if entry.content:
            indent = common.get_whitespace_prefix(entry.content)
            entry.content = textwrap.fill(
                entry.content, break_long_words=False, break_on_hyphens=False,
                initial_indent=indent, subsequent_indent=indent,
                max_lines=self._conf['max_lines'], width=self._conf['width'])
        yield entry
