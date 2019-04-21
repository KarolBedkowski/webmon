#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Abstract filter definition
"""

import abc
import typing as ty

from webmon import common, model

_ = ty


class AbstractFilter:
    """Base class for all filters.
    """

    name = None  # type: ty.Optional[str]
    params = []  # type: ty.List[ty.Any]
    stop_change_content = False

    def __init__(self, config: dict) -> None:
        super().__init__()
        self._conf = common.apply_defaults(
            {key: val for key, _desc, val, _req, _opt in self.params},
            config)  # type: ty.Dict[str, ty.Any]

    def dump_debug(self):
        return " ".join(("<", self.__class__.__name__, self.name,
                         repr(self._conf), ">"))

    def validate(self):
        """ Validate filter parameters """
        for name, _, _, required, _ in self.params or []:
            if required and not self._conf.get(name):
                raise common.ParamError("missing parameter " + name)

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        result = []  # type: ty.List[model.Entry]
        for entry in entries:
            result.extend(self._filter(entry))
        return result

    @abc.abstractmethod
    def _filter(self, entry: model.Entry) -> model.Entries:
        raise NotImplementedError()
