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

from webmon2 import common, model

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
            {key: val for (key, _desc, val, *_) in self.params},
            config)  # type: ty.Dict[str, ty.Any]

    def dump_debug(self):
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
        for name, description, _, required, _, vtype in cls.params or []:
            if not required:
                continue
            values = [conf[name] for conf in confs if conf.get(name)]
            if not values:
                yield (name, 'missing parameter "{}"'.format(description))
                continue
            try:
                vtype(values[0])
            except ValueError:
                yield (name, 'invalid value {!r} for "{}"'.format(
                    values[0], description))

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        result = []  # type: ty.List[model.Entry]
        for entry in entries:
            result.extend(self._filter(entry))
        return result

    @abc.abstractmethod
    def _filter(self, entry: model.Entry) -> model.Entries:
        raise NotImplementedError()

    @classmethod
    def get_param_types(cls) -> ty.Dict[str, str]:
        return {name: ptype for name, *_, ptype in cls.params}

    @classmethod
    def get_param_defaults(cls) -> ty.Dict[str, ty.Any]:
        return {name: default for name, _, default, *_ in cls.params
                if default is not None}
