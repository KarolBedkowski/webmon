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


from webmon import model, common


class AbstractInput:
    """ Abstract/Base class for all inputs """

    # name used in configuration
    name = None  # type: ty.Optional[str]
    # parameters - list of tuples (name, description, default, required,
    # options, type)
    params = []  # type: ty.List[ty.Tuple[str, str, ty.Any,bool,ty.Any,ty.Any]]

    def __init__(self, source: model.Source) -> None:
        super().__init__()
        self._source = source
        self._conf = common.apply_defaults(
            {key: val for key, _name, val, _req, _opts, _type in self.params},
            source.settings)

    def dump_debug(self):
        return " ".join(("<", self.__class__.__name__, str(self._source),
                         repr(self._conf), ">"))

    def validate(self):
        """ Validate input configuration """
        for name, _, _, required, *_ in self.params or []:
            val = self._conf.get(name)
            if required and val is None:
                raise common.ParamError("missing parameter " + name)

    def load(self, state: model.SourceState) -> \
            ty.Tuple[model.SourceState, ty.List[model.Entry]]:
        """ Load data; return list of items (Result).  """
        raise NotImplementedError()

    @classmethod
    def get_param_types(cls) -> ty.Dict[str, str]:
        return {name: ptype for name, *_, ptype in cls.params}

    @classmethod
    def get_param_defaults(cls) -> ty.Dict[str, ty.Any]:
        return {name: default for name, _, default, *_ in cls.params
                if default is not None}
