#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Abstract input definition
"""

import typing as ty
import logging

from webmon2 import model, common

_LOG = logging.getLogger(__name__)


class AbstractInput:
    """ Abstract/Base class for all inputs """

    # name used in configuration
    name = None  # type: ty.Optional[str]
    params = []  # type: ty.List[common.SettingDef]

    def __init__(self, source: model.Source,
                 sys_settings: ty.Dict[str, ty.Any]) -> None:
        super().__init__()
        self._source = source
        self._conf = common.apply_defaults(
            {param.name: param.default for param in self.params},
            sys_settings, source.settings)
        _LOG.debug("Source %s: conf: %r", source.id, self._conf)

    def dump_debug(self):
        return " ".join(("<", self.__class__.__name__, str(self._source),
                         repr(self._conf), ">"))

    def validate(self):
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

    def load(self, state: model.SourceState) -> \
            ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """ Load data; return list of items (Result).  """
        raise NotImplementedError()

    @classmethod
    def get_param_types(cls) -> ty.Dict[str, str]:
        return {param.name: param.type for param in cls.params}

    @classmethod
    def get_param_defaults(cls) -> ty.Dict[str, ty.Any]:
        return {param.name: param.default for param in cls.params}
