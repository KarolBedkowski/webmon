"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016-2022

This file is part of webmon.
Licence: GPLv2+
"""

from __future__ import annotations

import email.utils
import itertools
import pathlib
import typing as ty
from contextlib import suppress
from pathlib import Path

import structlog

if ty.TYPE_CHECKING:
    import datetime

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger("common")

ConfDict = dict[str, ty.Any]

Row = dict[str, ty.Any]


class ParamError(Exception):
    """Exception raised on missing param"""


class InputError(Exception):
    """Exception raised on command error"""

    def __init__(self, input_: ty.Any, msg: str) -> None:  # noqa:ANN401
        super().__init__(msg)
        self.input = input_


class FilterError(Exception):
    """Exception raised on command error"""

    def __init__(self, filter_: ty.Any, msg: str) -> None:  # noqa:ANN401
        super().__init__(msg)
        self.filter = filter_


class OperationError(RuntimeError):
    pass


ParentClass = ty.Any


def find_subclass(
    base_class: ParentClass, name: str
) -> ty.Optional[ty.Type[ParentClass]]:
    """Find subclass to given `base_class` with given value of
    attribute `name`"""

    for cname, clazz in get_subclasses_with_name(base_class):
        if cname == name:
            return clazz  # type: ignore

    return None


ParentClass2 = ty.Type[ty.Any]


def get_subclasses_with_name(
    base_class: ParentClass2,
) -> ty.Iterator[tuple[str, ty.Any]]:
    """Iter over subclasses and yield `name` attribute"""

    def find(
        parent_cls: ParentClass2,
    ) -> ty.Iterator[tuple[str, ParentClass2]]:
        for rcls in parent_cls.__subclasses__():
            if name := getattr(rcls, "name", None):
                yield name, rcls

            yield from find(rcls)

    yield from find(base_class)


def parse_interval(instr: str | float) -> int:
    """Parse interval in human readable format and return interval in sec."""
    if isinstance(instr, (int, float)):
        if instr < 1:
            errmsg = f"invalid interval '{instr!s}'"
            raise ValueError(errmsg)

        return int(instr)

    instr = instr.strip()
    if not instr:
        raise ValueError("invalid interval")

    mplt = 1
    match instr[-1].lower():
        case "m":
            mplt = 60
        case "h":
            mplt = 3_600
        case "d":
            mplt = 86_400
        case "w":
            mplt = 604_800

    if mplt != 1:
        instr = instr[:-1]

    try:
        val = int(instr)
    except ValueError as err:
        errmsg = f"invalid interval '{instr!s}'"
        raise ValueError(errmsg) from err

    if val < 1:
        raise ValueError("invalid interval - <1")

    return val * mplt


def apply_defaults(*confs: ty.Optional[ConfDict]) -> ConfDict:
    """Create dict from confs."""
    result = {}  # type: ConfDict
    for idx, conf in enumerate(confs):
        if conf:
            result.update(
                (key, val) for key, val in conf.items() if val or idx == 0
            )

    return result


def create_missing_dir(path: str) -> None:
    """Check path and if not exists create directory.
    If path exists and is not directory - raise error.
    """
    pat = Path(path).expanduser()
    if pat.exists():
        if pat.is_dir():
            return

        errmsg = f"path {path} exists and is not dir"
        raise RuntimeError(errmsg)

    pathlib.Path(path).mkdir(parents=True)


def is_whitespace(character: str) -> bool:
    return character in (" ", "\t")


def get_whitespace_prefix(text: str) -> str:
    """Get all whitespace characters from beginning of `text`"""
    return "".join(itertools.takewhile(is_whitespace, text))


def _parse_hour_min(text: str) -> int:
    match text.strip().split(":", 3):
        case [h]:
            return (int(h) % 24) * 60
        case [h, m] | [h, m, _]:
            # we ignore seconds
            return (int(h) % 24) * 60 + int(m) % 60

    return 0


def parse_hours_range(inp: str) -> ty.Iterable[tuple[int, int]]:
    """Parse hours ranges defined as:
        hour1[:minutes1]-hour2[:minutes](,hour1[:minutes1]-hour2[:minutes])+
    Returns iterable: (start_time, end_time) for each valid range
    start_time, end_time = int: hour * 60 + minutes
    """
    # pylint: disable=invalid-sequence-index
    inp = inp.replace(" ", "").expandtabs(0)
    for hrang in inp.split(","):
        if "-" not in hrang:
            continue

        start, stop = hrang.split("-")
        if not start or not stop:
            continue

        with suppress(ValueError):
            yield _parse_hour_min(start), _parse_hour_min(stop)


def check_date_in_timerange(tsrange: str, hour: int, minutes: int) -> bool:
    """Check is `hour`:`minutes` is in any time ranges defined in `tsrange`"""
    tshm = hour * 60 + minutes
    for rstart, rstop in parse_hours_range(tsrange):
        if rstart < rstop:
            if rstart <= tshm <= rstop:
                return True

        elif not rstop < tshm < rstart:
            return True

    return False


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class SettingDef:
    # pylint: disable=too-many-arguments
    def __init__(  # noqa:PLR0913
        self,
        name: str,
        description: str,
        default: ty.Any = None,  # noqa: ANN401
        required: bool = False,
        options: dict[str, ty.Any] | None = None,
        value_type: ty.Type[ty.Any] | None = None,
        global_param: bool = False,
        **kwargs: ty.Any,  # noqa: ANN401
    ) -> None:
        self.name = name
        self.description = description
        self.default = default
        self.required = required
        self.options = options
        self.parameters = kwargs
        self.type: ty.Type[ty.Any]

        if value_type is None:
            self.type = str if default is None else type(default)  # type:ignore
        else:
            self.type = value_type

        self.global_param = global_param

    def get_parameter(
        self,
        key: str,
        default: ty.Any = None,  # noqa: ANN401
    ) -> ty.Any:  # noqa: ANN401
        if self.parameters:
            return self.parameters.get(key, default)

        return default

    def validate_value(self, value: ty.Any) -> bool:  # noqa: ANN401
        if (
            self.required
            and self.default is None
            and (value is None or self.type == str and not value)
        ):
            return False

        try:
            self.type(value)
        except ValueError:
            return False

        return True


def _val2str(raw_value: ty.Any) -> str:  # noqa: ANN401
    value = str(raw_value)
    if len(value) > 64:  # noqa:PLR2004
        return value[:64] + "..."

    return value


def obj2str(obj: ty.Any) -> str:  # noqa: ANN401
    if hasattr(obj, "__dict__"):
        values = obj.__dict__.items()
    else:
        values = ((key, getattr(obj, key)) for key in obj.__slots__)

    kvs = ", ".join(
        [f"{key}={_val2str(val)}" for key, val in values if key[0] != "_"]
    )

    return f"<{obj.__class__.__name__} {kvs}>"


def parse_http_date(date: str | None) -> datetime.datetime | None:
    """Parse date in format 'Sat, 03 Aug 2019 21:38:14 GMT' and change
    timezone to local"""
    if not date:
        return None

    try:
        return email.utils.parsedate_to_datetime(date)
    except TypeError:
        pass
    except ValueError as err:
        _LOG.debug("common: parse_http_date: date: %r, error", date, error=err)

    return None


def parse_form_list_data(
    form: dict[str, ty.Any], prefix: str
) -> ty.Iterable[dict[str, ty.Any]]:
    """Parse form data named <prefix>-<idx>-<name> to
    enumeration[{<name>: <value>}]
    for each idx and matched prefix
    """
    values = {}
    for key, val in form.items():
        try:
            kprefix, kidx_s, kname = key.split("-")
            kidx = int(kidx_s)
        except (ValueError, TypeError):
            continue

        if kprefix != prefix:
            continue

        if kidx not in values:
            values[kidx] = {kname: val, "__idx": kidx}
        else:
            values[kidx][kname] = val

    for _, val in sorted(values.items()):
        yield val


def parse_str_to_headers(instr: str | None) -> ty.Iterator[tuple[str, str]]:
    """Parse text to headers.
    `instr` contains one header per line; header name is separated from
    value by `:`.
    """
    if not instr:
        return

    for header in instr.split("\n"):
        if not header:
            continue

        key, sep, val = header.partition(":")
        if sep and (key := key.strip()):
            yield key, val.strip()
