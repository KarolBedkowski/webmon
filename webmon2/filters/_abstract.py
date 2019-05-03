#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Abstract filter definition
"""

import abc
import typing as ty

from webmon2 import common, model

_ = ty


class AbstractFilter:
    """Base class for all filters.
    """

    name = None  # type: ty.Optional[str]
    params = []  # type: ty.List[common.SettingDef]

    def __init__(self, config: dict) -> None:
        super().__init__()
        self._conf = common.apply_defaults(
            {param.name: param.default for param in self.params},
            config)  # type: ty.Dict[str, ty.Any]

    def __str__(self):
        return " ".join(("<", self.__class__.__name__, self.name,
                         repr(self._conf), ">"))

    def validate(self):
        """ Validate filter parameters """
        for name, error in self.validate_conf(self._conf):
            raise common.ParamError("parameter {} error {}".format(
                name, error))

    @classmethod
    def validate_conf(cls, *confs) -> ty.Iterable[ty.Tuple[str, str]]:
        """ Validate input configuration.
            Returns  iterable of (<parameter>, <error>)
        """
        for param in cls.params or []:
            if not param.required:
                continue
            values = [conf[param.name] for conf in confs
                      if conf.get(param.name)]
            if not values:
                yield (param.name,
                       'missing parameter "{}"'.format(param.description))
                continue
            if not param.validate_value(values[0]):
                yield (param.name, 'invalid value {!r} for "{}"'.format(
                    values[0], param.description))

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        for entry in entries:
            yield from self._filter(entry)

    @abc.abstractmethod
    def _filter(self, entry: model.Entry) -> model.Entries:
        raise NotImplementedError()

    @classmethod
    def get_param_types(cls) -> ty.Dict[str, str]:
        return {param.name: param.type for param in cls.params}

    @classmethod
    def get_param_defaults(cls) -> ty.Dict[str, ty.Any]:
        return {param.name: param.default for param in cls.params}
