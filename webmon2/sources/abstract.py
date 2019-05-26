#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Abstract source definition
"""

import typing as ty
import logging

import requests

from webmon2 import model, common

_LOG = logging.getLogger(__name__)


class AbstractSource:
    """ Abstract/Base class for all sources """

    # name used in configuration
    name = None  # type: ty.Optional[str]
    params = []  # type: ty.List[common.SettingDef]
    short_info = ""
    long_info = ""

    AGENT = ("Mozilla/5.0 (X11; Linux i686; rv:45.0) "
             "Gecko/20100101 Firefox/45.0")

    def __init__(self, source: model.Source,
                 sys_settings: ty.Dict[str, ty.Any]) -> None:
        super().__init__()
        self._source = source
        self._updated_source = None
        self._conf = common.apply_defaults(
            {param.name: param.default for param in self.params},
            sys_settings, source.settings)
        _LOG.debug("Source %s: conf: %r", source.id, self._conf)

    def __str__(self):
        return " ".join(("<", self.__class__.__name__, str(self._source),
                         repr(self._conf), ">"))

    def validate(self):
        for name, error in self.validate_conf(self._conf):
            raise common.ParamError("parameter {} error {}".format(
                name, error))

    @property
    def updated_source(self) -> ty.Optional[model.Source]:
        return self._updated_source

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

    def _load_binary(self, url):
        _LOG.debug("loading binary %s", url)
        try:
            response = requests.request(
                url=url, method='GET', headers={"User-agent": self.AGENT},
                allow_redirects=True)
            if response:
                response.raise_for_status()
                if response.status_code == 200:
                    return response.headers['Content-Type'], response.content
                _LOG.info("load binary from %s status %s error: %s", url,
                          response.status_code, response.text)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("load binary from %s error: %s", url, err)
        return None

    @classmethod
    def get_param_types(cls) -> ty.Dict[str, str]:
        return {param.name: param.type for param in cls.params}

    @classmethod
    def get_param_defaults(cls) -> ty.Dict[str, ty.Any]:
        return {param.name: param.default for param in cls.params}

    @classmethod
    def to_opml(cls, source: model.Source) -> ty.Dict[str, ty.Any]:
        raise NotImplementedError()

    @classmethod
    def from_opml(cls, opml_node: ty.Dict[str, ty.Any]) \
            -> ty.Optional[model.Source]:
        raise NotImplementedError()
