# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Abstract filter definition
"""

from __future__ import annotations

import abc
import typing as ty

from webmon2 import common, database, model


class AbstractFilter(abc.ABC):
    """Base class for all filters."""

    name: str = None  # type: ignore
    short_info = ""
    long_info = ""
    params: tuple[common.SettingDef, ...] = ()

    def __init__(self, config: model.ConfDict) -> None:
        super().__init__()
        self.db: database.DB | None = None
        self._conf: model.ConfDict = common.apply_defaults(
            {param.name: param.default for param in self.params}, config
        )

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} {self._conf!r}>"

    def validate(self) -> None:
        """Validate filter parameters"""
        for name, error in self.validate_conf(self._conf):
            errmsg = f"parameter {name} error {error}"
            raise common.ParamError(errmsg)

    @classmethod
    def validate_conf(
        cls: ty.Type[ty.Self], *confs: model.ConfDict
    ) -> ty.Iterable[tuple[str, str]]:
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

    # pylint: disable=unused-argument
    def filter(
        self,
        entries: model.Entries,
        prev_state: model.SourceState,  # noqa:ARG002
        curr_state: model.SourceState,  # noqa:ARG002
    ) -> model.Entries:
        for entry in entries:
            yield from self._filter(entry)

    @abc.abstractmethod
    def _filter(self, entry: model.Entry) -> model.Entries:
        raise NotImplementedError

    @classmethod
    def get_param_types(cls: ty.Type[ty.Self]) -> dict[str, ty.Type[ty.Any]]:
        return {param.name: param.type for param in cls.params}

    @classmethod
    def get_param_defaults(cls: ty.Type[ty.Self]) -> dict[str, ty.Any]:
        return {param.name: param.default for param in cls.params}
