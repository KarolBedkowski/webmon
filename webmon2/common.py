"""
Commons elements - errors etc

Copyright (c) Karol Będkowski, 2016-2022

This file is part of webmon.
Licence: GPLv2+
"""

import datetime
import email.utils
import functools
import itertools
import logging
import os.path
import pathlib
import typing as ty
from contextlib import suppress
from pathlib import Path

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2022"


_LOG = logging.getLogger("common")

ConfDict = dict[str, ty.Any]

Row = dict[str, ty.Any]


class ParamError(Exception):
    """Exception raised on missing param"""


class InputError(Exception):
    """Exception raised on command error"""

    def __init__(self, input_: ty.Any, msg: str):
        super().__init__(msg)
        self.input = input_


class FilterError(Exception):
    """Exception raised on command error"""

    def __init__(self, filter_: ty.Any, msg: str):
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
) -> ty.Iterator[ty.Tuple[str, ty.Any]]:
    """Iter over subclasses and yield `name` attribute"""

    def find(
        parent_cls: ParentClass2,
    ) -> ty.Iterator[ty.Tuple[str, ParentClass2]]:
        for rcls in getattr(parent_cls, "__subclasses__")():
            name = getattr(rcls, "name")
            if name:
                yield name, rcls

            yield from find(rcls)

    yield from find(base_class)


def parse_interval(instr: ty.Union[str, float, int]) -> int:
    """Parse interval in human readable format and return interval in sec."""
    if isinstance(instr, (int, float)):
        if instr < 1:
            raise ValueError(f"invalid interval '{instr!s}'")
        return int(instr)

    instr = instr.lower().strip()
    mplt = 1
    if instr.endswith("m"):
        mplt = 60
        instr = instr[:-1]
    elif instr.endswith("h"):
        mplt = 3600
        instr = instr[:-1]
    elif instr.endswith("d"):
        mplt = 86400
        instr = instr[:-1]
    elif instr.endswith("w"):
        mplt = 604800
        instr = instr[:-1]
    try:
        val = int(instr) * mplt
        if val < 1:
            raise ValueError("invalid interval - <1")
        return val
    except ValueError as err:
        raise ValueError(f"invalid interval '{instr!s}'") from err


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
    path = os.path.expanduser(path)
    pat = Path(path)
    if pat.exists():
        if pat.is_dir():
            return
        raise RuntimeError(f"path {path} exists and is not dir")

    pathlib.Path(path).mkdir(parents=True)


def is_whitespace(character: str) -> bool:
    return character in (" ", "\t")


def get_whitespace_prefix(text: str) -> str:
    """Get all whitespace characters from beginning of `text`"""
    return "".join(itertools.takewhile(is_whitespace, text))


def _parse_hour_min(text: str) -> int:
    hours = 0  # type: int
    minutes = 0  # type: int
    text = text.strip()
    if ":" in text:
        hours_str, minutes_str, *_ = text.split(":", 3)
        hours = int(hours_str) % 24
        minutes = int(minutes_str) % 60
    else:
        hours = int(text) % 24

    return hours * 60 + minutes


def parse_hours_range(inp: str) -> ty.Iterable[ty.Tuple[int, int]]:
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
            start_hm = _parse_hour_min(start)
            stop_hm = _parse_hour_min(stop)
            yield (start_hm, stop_hm)


def check_date_in_timerange(tsrange: str, hour: int, minutes: int) -> bool:
    """Check is `hour`:`minutes` is in any time ranges defined in `tsrange`"""
    tshm = hour * 60 + minutes
    for rstart, rstop in parse_hours_range(tsrange):
        print((rstart, rstop, tshm))
        if rstart < rstop:
            if rstart <= tshm <= rstop:
                return True
        else:
            if not rstop < tshm < rstart:
                return True
    return False


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class SettingDef:
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        name: str,
        description: str,
        default: ty.Optional[ty.Any] = None,
        required: bool = False,
        options: ty.Optional[dict[str, ty.Any]] = None,
        value_type: ty.Optional[ty.Type[ty.Any]] = None,
        global_param: bool = False,
        **kwargs: ty.Any,
    ):
        self.name = name
        self.description = description
        self.default = default
        self.required = required
        self.options = options
        self.parameters = kwargs
        self.type: ty.Type[ty.Any]
        if value_type is None:
            if default is None:
                self.type = str
            else:
                self.type = type(default)
        else:
            self.type = value_type

        self.global_param = global_param

    def get_parameter(self, key: str, default: ty.Any = None) -> ty.Any:
        if self.parameters:
            return self.parameters.get(key, default)

        return default

    def validate_value(self, value: ty.Any) -> bool:
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


def _val2str(raw_value: ty.Any) -> str:
    value = str(raw_value)
    if len(value) > 64:
        return value[:64] + "..."

    return value


def obj2str(obj: ty.Any) -> str:
    if hasattr(obj, "__dict__"):
        values = obj.__dict__.items()
    else:
        values = (
            (key, getattr(obj, key)) for key in getattr(obj, "__slots__")
        )
    kvs = ", ".join(
        [key + "=" + _val2str(val) for key, val in values if key[0] != "_"]
    )
    return f"<{obj.__class__.__name__} {kvs}>"


def parse_http_date(date: ty.Optional[str]) -> ty.Optional[datetime.datetime]:
    """Parse date in format 'Sat, 03 Aug 2019 21:38:14 GMT' and change
    timezone to local"""
    if not date:
        return None

    try:
        return email.utils.parsedate_to_datetime(date)
    except TypeError:
        pass
    except ValueError as err:
        _LOG.debug("parse_http_date '%s' error: %s", date, err)

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


CacheFuncRes = ty.TypeVar("CacheFuncRes")


def _cache(
    func: ty.Callable[..., CacheFuncRes]
) -> ty.Callable[..., CacheFuncRes]:
    """Run function once and cache results."""

    def wrapper(*args: ty.Any, **kwargs: ty.Any) -> CacheFuncRes:
        if not wrapper.has_run:  # type: ignore
            wrapper.has_run = True  # type: ignore

            wrapper.result = func(*args, **kwargs)  # type: ignore

        return wrapper.result  # type: ignore

    wrapper.has_run = False  # type: ignore
    return wrapper


# functools.cache is available in 3.9+
# FIXME: remove
cache: ty.Callable[[ty.Callable[..., ty.Any]], ty.Any] = (
    functools.cache if hasattr(functools, "cache") else _cache
)
