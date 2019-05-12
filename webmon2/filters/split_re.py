#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Split entry by regexp

"""
import typing as ty
import logging
import re

from webmon2 import model, common

from ._abstract import AbstractFilter

_ = ty
_LOG = logging.getLogger(__name__)


class SelectByRE(AbstractFilter):
    """Extract elements from html/xml by re expression"""

    name = "get-elements-by-re"
    short_info = "Extract elements by regular expression"
    long_info = "Search and extract element from content by given regular " \
        "expression. Expression must contain at least one group; can also " \
        "contain groups 'title' and 'content'."
    params = [
        common.SettingDef("re", "selector", required=True),
    ]  # type: ty.List[common.SettingDef]

    def __init__(self, conf):
        super().__init__(conf)
        self._re = re.compile(conf['re'],
                              re.IGNORECASE | re.LOCALE | re.MULTILINE)

    def validate(self):
        super().validate()
        try:
            self._re = re.compile(self._conf["sel"],
                                  re.IGNORECASE | re.LOCALE | re.MULTILINE)
        except Exception:  # pylint: disable=broad-except
            raise ValueError('Invalid re selector for filtering')

    def _filter(self, entry: model.Entry) -> model.Entries:
        for match in self._re.finditer(entry.content):
            if not match:
                continue
            groupdict = match.groupdict()
            if groupdict:
                content = groupdict.get('content') or match.groups()[0]
                title = groupdict.get('title')
                yield _new_entry(entry, content, title)
            else:
                yield _new_entry(entry, match.group())


def _new_entry(entry, content, title=None):
    new_entry = entry.clone()
    new_entry.status = 'new'
    if title:
        new_entry.title = title
    new_entry.content = content
    return new_entry