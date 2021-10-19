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

import logging
import typing as ty

import requests

from webmon2 import common, model

_LOG = logging.getLogger(__name__)


class AbstractSource:
    """Abstract/Base class for all sources"""

    # name used in configuration
    name = None  # type: ty.Optional[str]
    params = []  # type: ty.List[common.SettingDef]
    short_info = ""
    long_info = ""

    AGENT = (
        "Mozilla/5.0 (X11; Linux i686; rv:45.0) Gecko/20100101 Firefox/45.0"
    )

    def __init__(
        self, source: model.Source, sys_settings: model.ConfDict
    ) -> None:
        super().__init__()
        self._source = source
        self._updated_source = None  # type: ty.Optional[model.Source]
        self._conf: model.ConfDict = common.apply_defaults(
            {param.name: param.default for param in self.params},
            sys_settings,
            source.settings,
        )
        _LOG.debug("Source %s: conf: %r", source.id, self._conf)

    def __str__(self):
        return " ".join(
            (
                "<",
                self.__class__.__name__,
                str(self._source),
                repr(self._conf),
                ">",
            )
        )

    def validate(self):
        for name, error in self.validate_conf(self._conf):
            raise common.ParamError(f"parameter {name} error {error}")

    @property
    def updated_source(self) -> ty.Optional[model.Source]:
        return self._updated_source

    @classmethod
    def validate_conf(
        cls, *confs: model.ConfDict
    ) -> ty.Iterable[ty.Tuple[str, str]]:
        """Validate input configuration.
        Returns  iterable of (<parameter>, <error>)
        """
        for param in cls.params or []:
            if not param.required:
                continue

            values = [
                conf[param.name] for conf in confs if conf.get(param.name)
            ]
            if not values:
                yield (param.name, f'missing parameter "{param.description}"')
                continue

            if not param.validate_value(values[0]):
                yield (
                    param.name,
                    f'invalid value {values[0]!r} for "{param.description}"',
                )

    def load(
        self, state: model.SourceState
    ) -> ty.Tuple[model.SourceState, model.Entries]:
        """Load data; return list of items (Result)."""
        raise NotImplementedError()

    def _load_binary(
        self, url, only_images=True
    ) -> ty.Optional[ty.Tuple[str, bytes]]:
        _LOG.debug("loading binary %s", url)
        try:
            response = requests.request(
                url=url,
                method="GET",
                headers={"User-agent": self.AGENT},
                allow_redirects=True,
            )
            if response:
                response.raise_for_status()
                if response.status_code == 200:
                    if only_images and not _check_content_type(
                        response, _IMAGE_TYPES
                    ):
                        _LOG.info(
                            "load binary from %s skipped due not "
                            "acceptable content type: %s",
                            url,
                            response.headers["Content-Type"],
                        )
                        return None

                    return response.headers["Content-Type"], response.content

                _LOG.info(
                    "load binary from %s status %s error: %s",
                    url,
                    response.status_code,
                    response.text,
                )
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
    def from_opml(
        cls, opml_node: ty.Dict[str, ty.Any]
    ) -> ty.Optional[model.Source]:
        raise NotImplementedError()


_IMAGE_TYPES = set(
    (
        "image/png",
        "image/x-icon",
        "image/vnd.microsoft.icon",
    )
)


def _check_content_type(response, accepted: ty.Iterable[str]) -> bool:
    content_type = response.headers["Content-Type"]
    return content_type in accepted
