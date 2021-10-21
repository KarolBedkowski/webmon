#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2021
#
# Distributed under terms of the GPLv3 license.
# pylint: disable=too-many-arguments

"""
Models
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import typing as ty
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, IntEnum

from webmon2 import common, formatters
from webmon2.database._db import tyCursor

_LOG = logging.getLogger(__name__)


ConfDict = ty.Dict[str, ty.Any]


class MailReportMode(IntEnum):
    NO_SEND = 0
    AS_GROUP_SOURCE = 1
    SEND = 2


@dataclass
class SourceGroup:
    # name of group
    name: str
    user_id: int
    # id of source group
    id: ty.Optional[int] = None
    # feed url - hash part
    feed: ty.Optional[str] = None
    # configuration of mail sending for this group
    mail_report: MailReportMode = MailReportMode.AS_GROUP_SOURCE
    # number of unread entries in group / not in source_groups table
    unread: bool = False
    # number of sources in group / not in source_groups table
    sources_count: int = 0

    def __str__(self) -> str:
        return common.obj2str(self)

    def clone(self) -> SourceGroup:
        sgr = SourceGroup(
            id=self.id,
            name=self.name,
            user_id=self.user_id,
            feed=self.feed,
            mail_report=self.mail_report,
            sources_count=self.sources_count,
        )
        return sgr

    @classmethod
    def from_row(cls, row: tyCursor) -> SourceGroup:
        return SourceGroup(
            id=row["source_group__id"],
            name=row["source_group__name"],
            user_id=row["source_group__user_id"],
            feed=row["source_group__feed"],
            mail_report=MailReportMode(row["source_group__mail_report"]),
        )

    def to_row(self) -> common.Row:
        return {
            "source_group__id": self.id,
            "source_group__name": self.name,
            "source_group__user_id": self.user_id,
            "source_group__feed": self.feed,
            "source_group__mail_report": self.mail_report.value,
        }


class SourceStatus(IntEnum):
    # source not activated after configuration
    NOT_ACTIVATED = 0
    # source is active
    ACTIVE = 1
    # source disabled by user
    DISABLED = 2


class Source:  # pylint: disable=too-many-instance-attributes
    __slots__ = (
        "id",
        "group_id",
        "kind",
        "name",
        "interval",
        "settings",
        "filters",
        "user_id",
        "group",
        "state",
        "unread",
        "status",
        "mail_report",
        "default_score",
    )

    def __init__(self, user_id: int, name: str, kind: str, group_id: int):
        self.id: int = 0
        self.group_id: int = group_id
        # source kind name - using to select class supported this source
        self.kind: str = kind
        self.name: str = name
        # update interval
        self.interval: ty.Optional[str] = None
        # additional settings
        self.settings: ty.Optional[ty.Dict[str, ty.Any]] = None
        # filters configuration
        self.filters: ty.List[ty.Dict[str, ty.Any]] = []
        self.user_id: int = user_id
        # status of source
        self.status: SourceStatus = SourceStatus.NOT_ACTIVATED
        # mail sending setting
        self.mail_report: MailReportMode = MailReportMode.AS_GROUP_SOURCE
        # default score given for entries this source
        self.default_score: int = 0

        self.group: ty.Optional[SourceGroup] = None
        self.state: ty.Optional[SourceState] = None
        # is source has unread entries
        self.unread: ty.Optional[int] = None

    def __str__(self) -> str:
        return common.obj2str(self)

    def clone(self) -> Source:
        src = Source(
            user_id=self.user_id,
            kind=self.kind,
            name=self.name,
            group_id=self.group_id,
        )
        src.id = self.id
        src.interval = self.interval
        src.settings = self.settings
        src.filters = self.filters
        src.status = self.status
        src.mail_report = self.mail_report
        src.default_score = self.default_score
        return src

    @classmethod
    def from_row(cls, row: tyCursor) -> Source:
        source = Source(
            user_id=row["source__user_id"],
            kind=row["source__kind"],
            name=row["source__name"],
            group_id=row["source__group_id"],
        )
        source.id = row["source__id"]
        source.interval = row["source__interval"]
        row_keys = row.keys()
        source.settings = common.get_json_if_exists(
            row_keys, "source__settings", row
        )
        source.filters = common.get_json_if_exists(
            row_keys, "source__filters", row
        )
        source.status = SourceStatus(row["source__status"])
        mail_report = row["source__mail_report"]
        if mail_report is None:
            source.mail_report = MailReportMode.AS_GROUP_SOURCE
        else:
            source.mail_report = MailReportMode(mail_report)
        source.default_score = row["source__default_score"]
        return source

    def to_row(self) -> common.Row:
        return {
            "source__group_id": self.group_id,
            "source__kind": self.kind,
            "source__name": self.name,
            "source__interval": self.interval,
            "source__settings": (
                json.dumps(self.settings) if self.settings else None
            ),
            "source__filters": (
                json.dumps(self.filters) if self.filters else None
            ),
            "source__user_id": self.user_id,
            "source__status": self.status.value,
            "source__id": self.id,
            "source__mail_report": self.mail_report.value
            if self.mail_report
            else None,
            "source__default_score": self.default_score,
        }


Sources = ty.Iterable[Source]


class SourceStateStatus(Enum):
    # new source stare; not jet updated
    NEW = "new"
    # source update error
    ERROR = "error"
    # source not modified
    NOT_MODIFIED = "not modified"
    # source updated
    OK = "ok"


States = ty.Dict[str, ty.Any]
IconData = ty.Tuple[str, bytes]


class SourceState:  # pylint: disable=too-many-instance-attributes
    __slots__ = (
        "source_id",
        "next_update",
        "last_update",
        "last_error",
        "error_counter",
        "success_counter",
        "status",
        "error",
        "state",
        "icon",
        "icon_data",
    )

    def __init__(self) -> None:
        self.source_id: int = 0
        # next source update time
        self.next_update: ty.Optional[datetime] = None
        # last source update time
        self.last_update: ty.Optional[datetime] = None
        # last source update failed time
        self.last_error: ty.Optional[datetime] = None
        # number of failed updates since last success update
        self.error_counter: int = 0
        # number of success updated since last failure
        self.success_counter: int = 0
        # source updates status
        self.status: ty.Optional[SourceStateStatus] = None
        self.error: ty.Optional[str] = None
        # additional informations stored by source loader
        self.state: ty.Optional[States] = None
        # icon hash
        self.icon: ty.Optional[str] = None

        # icon as binary data; loaded from binaries
        self.icon_data: ty.Optional[IconData] = None

    @staticmethod
    def new(source_id: int) -> SourceState:
        source = SourceState()
        source.source_id = source_id
        source.next_update = datetime.now() + timedelta(minutes=15)
        source.error_counter = 0
        source.success_counter = 0
        return source

    def create_new(self) -> SourceState:
        new_state = SourceState()
        new_state.source_id = self.source_id
        new_state.error_counter = self.error_counter
        new_state.success_counter = self.success_counter
        new_state.icon = self.icon
        return new_state

    def new_ok(self, **states: States) -> SourceState:
        state = SourceState()
        state.source_id = self.source_id
        state.last_update = datetime.now()
        state.status = SourceStateStatus.OK
        state.success_counter = self.success_counter + 1
        state.last_error = None
        state.error = None
        state.error_counter = 0
        state.state = self.state.copy() if self.state else None
        state.icon = self.icon
        state.update_state(states)
        return state

    def new_error(self, error: str, **states: States) -> SourceState:
        state = SourceState()
        state.source_id = self.source_id
        state.error = error
        state.last_update = self.last_update
        state.status = SourceStateStatus.ERROR
        state.success_counter = self.success_counter
        state.error_counter = self.error_counter + 1
        state.last_error = datetime.now()
        state.state = self.state.copy() if self.state else None
        state.icon = self.icon
        state.update_state(states)
        return state

    def new_not_modified(self, **states: States) -> SourceState:
        state = SourceState()
        state.source_id = self.source_id
        state.last_update = datetime.now()
        state.status = SourceStateStatus.NOT_MODIFIED
        state.last_error = None
        state.error = None
        state.error_counter = 0
        state.success_counter = self.success_counter + 1
        state.state = self.state.copy() if self.state else None
        state.icon = self.icon
        state.update_state(states)
        return state

    def set_state(self, key: str, value: ty.Any) -> None:
        if self.state is None:
            self.state = {key: value}
        else:
            self.state[key] = value

    def get_state(self, key: str, default: ty.Any = None) -> ty.Any:
        return self.state.get(key, default) if self.state else default

    def update_state(self, states: ty.Optional[States]) -> None:
        if not states:
            return

        if not self.state:
            self.state = {}

        self.state.update(states)

    def set_icon(
        self, content_type_data: ty.Optional[ty.Tuple[str, bytes]]
    ) -> ty.Optional[str]:
        if not content_type_data:
            return self.icon

        self.icon = hashlib.sha1(content_type_data[1]).hexdigest()
        self.icon_data = content_type_data
        return self.icon

    def __str__(self) -> str:
        return common.obj2str(self)

    def to_row(self) -> common.Row:
        return {
            "source_state__source_id": self.source_id,
            "source_state__next_update": self.next_update,
            "source_state__last_update": self.last_update,
            "source_state__last_error": self.last_error,
            "source_state__error_counter": self.error_counter,
            "source_state__success_counter": self.success_counter,
            "source_state__status": self.status.value if self.status else None,
            "source_state__error": self.error,
            "source_state__state": json.dumps(self.state),
            "source_state__icon": self.icon,
        }

    @classmethod
    def from_row(cls, row: tyCursor) -> SourceState:
        state = SourceState()
        state.source_id = row["source_state__source_id"]
        state.next_update = row["source_state__next_update"]
        state.last_update = row["source_state__last_update"]
        state.last_error = row["source_state__last_error"]
        state.error_counter = row["source_state__error_counter"]
        state.success_counter = row["source_state__success_counter"]
        state.status = SourceStateStatus(row["source_state__status"])
        state.error = row["source_state__error"]
        row_keys = row.keys()
        state.state = common.get_json_if_exists(
            row_keys, "source_state__state", row
        )
        state.icon = row["source_state__icon"]
        return state


class EntryStatus(Enum):
    # entry is new
    NEW = "new"
    # entry was updated
    UPDATED = "updated"


class EntryReadMark(IntEnum):
    # unread entry
    UNREAD = 0
    # send or mark read without read
    READ = 1
    # opened and read
    MANUAL_READ = 2


T = ty.TypeVar("T")


class Entry:  # pylint: disable=too-many-instance-attributes
    __slots__ = (
        "id",
        "source_id",
        "updated",
        "created",
        "read_mark",
        "star_mark",
        "status",
        "oid",
        "title",
        "url",
        "content",
        "opts",
        "icon",
        "user_id",
        "source",
        "icon_data",
        "score",
    )

    def __init__(
        self, id_: ty.Optional[int] = None, source_id: ty.Optional[int] = None
    ):
        self.id: int = id_  # type: ignore
        self.source_id: int = source_id  # type: ignore
        # time of entry updated
        self.updated: ty.Optional[datetime] = None
        # time of entry created
        self.created: ty.Optional[datetime] = None
        # is entry is read
        self.read_mark: EntryReadMark = EntryReadMark.UNREAD
        # is entry is marked
        self.star_mark: bool = False
        # entry status, new or updated for changed entries (not used)
        self.status: EntryStatus = EntryStatus.NEW
        # unique hash for entry
        self.oid: ty.Optional[str] = None
        self.title: ty.Optional[str] = None
        # url associated to entry
        self.url: ty.Optional[str] = None
        self.content: ty.Optional[str] = None
        # additional information about entry; ie. content type
        self.opts: ty.Optional[ty.Dict[str, ty.Any]] = None
        self.user_id: int = None  # type: ignore
        # hash of icon, from binaries table
        self.icon: ty.Optional[str] = None
        self.score = 0  # type; int

        # icon as data - tuple(content type, data)
        self.icon_data: ty.Optional[ty.Tuple[str, ty.Any]] = None
        self.source: ty.Optional[Source] = None

    def __str__(self) -> str:
        return common.obj2str(self)

    def clone(self) -> Entry:
        entry = Entry(source_id=self.source_id)
        entry.updated = self.updated
        entry.created = self.created
        entry.read_mark = self.read_mark
        entry.star_mark = self.star_mark
        entry.status = self.status
        entry.oid = self.oid
        entry.title = self.title
        entry.url = self.url
        entry.opts = self.opts.copy() if self.opts else None
        entry.content = self.content
        entry.user_id = self.user_id
        entry.icon = self.icon
        entry.icon_data = self.icon_data
        entry.score = self.score
        return entry

    @staticmethod
    def for_source(source: Source) -> Entry:
        entry = Entry(source_id=source.id)
        entry.user_id = source.user_id
        entry.score = source.default_score or 0
        return entry

    def calculate_oid(self) -> str:
        data = "".join(
            map(str, (self.source_id, self.title, self.url, self.content))
        )
        csum = hashlib.sha1(data.encode("utf-8"))
        self.oid = base64.b64encode(csum.digest()).decode("ascii")
        return self.oid

    def get_opt(
        self, key: str, default: ty.Optional[T] = None
    ) -> ty.Optional[T]:
        return self.opts.get(key, default) if self.opts else default

    def set_opt(self, key: str, value: ty.Any) -> None:
        if self.opts is None:
            self.opts = {}

        self.opts[key] = value

    def human_title(self) -> str:
        if self.title:
            return self.title

        if not self.content:
            return "<no title>"

        if len(self.content) > 50:
            return self.content[:50] + "…"

        return self.content

    def is_long_content(self) -> bool:
        if self.content:
            lines = self.content.count("\n")
            characters = len(self.content)
            return lines > 10 or characters > 400

        return False

    def _get_content_type(self) -> ty.Optional[str]:
        return self.get_opt("content-type")

    def _set_content_type(self, content_type: str) -> None:
        if self.opts is None:
            self.opts = {}

        self.opts["content-type"] = content_type

    content_type = property(_get_content_type, _set_content_type)

    def get_summary(self) -> ty.Optional[str]:
        return formatters.entry_summary(self.content, self._get_content_type())

    def validate(self) -> None:
        if not isinstance(self.updated, datetime):
            _LOG.error("wrong entry.updated:  %r (%r)", self.updated, self)

        if not isinstance(self.created, datetime):
            _LOG.error("wrong entry.created:  %r (%r)", self.created, self)

        if not self.title:
            _LOG.error("missing title %s", self)

    def calculate_icon_hash(self) -> ty.Optional[str]:
        if not self.icon_data:
            return self.icon

        try:
            self.icon = hashlib.sha1(self.icon_data[1]).hexdigest()
        except Exception as err:  # pylint: disable=broad-except
            _LOG.error("hasing %r error: %s", self.icon_data, err)

        return self.icon

    def to_row(self) -> common.Row:
        return {
            "entry__source_id": self.source_id,
            "entry__updated": self.updated,
            "entry__created": self.created,
            "entry__read_mark": self.read_mark.value,
            "entry__star_mark": 1 if self.star_mark else 0,
            "entry__status": self.status.value,
            "entry__oid": self.oid,
            "entry__title": self.title,
            "entry__url": self.url,
            "entry__opts": json.dumps(self.opts),
            "entry__content": self.content,
            "entry__id": self.id,
            "entry__user_id": self.user_id,
            "entry__icon": self.icon,
            "entry__score": self.score,
        }

    @classmethod
    def from_row(cls, row: tyCursor) -> Entry:
        entry = Entry(row["entry__id"])
        entry.source_id = row["entry__source_id"]
        entry.updated = row["entry__updated"]
        entry.created = row["entry__created"]
        entry.read_mark = EntryReadMark(row["entry__read_mark"])
        entry.star_mark = bool(row["entry__star_mark"])
        entry.status = row["entry__status"]
        entry.oid = row["entry__oid"]
        entry.title = row["entry__title"]
        entry.url = row["entry__url"]
        row_keys = row.keys()
        entry.opts = common.get_json_if_exists(row_keys, "entry__opts", row)
        if "entry__content" in row_keys:
            entry.content = row["entry__content"]

        entry.user_id = row["entry__user_id"]
        entry.icon = row["entry__icon"]
        entry.score = row["entry__score"]
        return entry


Entries = ty.Iterable[Entry]


@dataclass
class Setting:
    key: str
    value: ty.Any
    value_type: str
    description: str
    # user id if settings is for given user
    user_id: ty.Optional[int] = None

    def __str__(self) -> str:
        return common.obj2str(self)

    @classmethod
    def from_row(cls, row: tyCursor) -> Setting:
        value = row["setting__value"]
        if value and isinstance(value, str):
            value = json.loads(value)

        return Setting(
            key=row["setting__key"],
            value=value,
            value_type=row["setting__value_type"],
            description=row["setting__description"],
            user_id=row["setting__user_id"],
        )

    def to_row(self) -> common.Row:
        return {
            "setting__key": self.key,
            "setting__value": json.dumps(self.value),
            "setting__value_type": self.value_type,
            "setting__description": self.description,
            "setting__user_id": self.user_id,
        }


@dataclass
class User:
    id: ty.Optional[int] = None
    login: ty.Optional[str] = None
    email: ty.Optional[str] = None
    password: ty.Optional[str] = None
    active: bool = True
    admin: bool = False
    # totp token if user configure totp
    totp: ty.Optional[str] = None

    @classmethod
    def from_row(cls, row: tyCursor) -> User:
        return User(
            id=row["user__id"],
            login=row["user__login"],
            email=row["user__email"],
            password=row["user__password"],
            active=row["user__active"],
            admin=row["user__admin"],
            totp=row["user__totp"],
        )

    def to_row(self) -> common.Row:
        return {
            "user__id": self.id,
            "user__login": self.login,
            "user__email": self.email,
            "user__password": self.password,
            "user__active": self.active,
            "user__admin": self.admin,
            "user__totp": self.totp,
        }

    def clone(self) -> User:
        user = User(
            id=self.id,
            login=self.login,
            email=self.email,
            password=self.password,
            active=self.active,
            admin=self.admin,
            totp=self.totp,
        )
        return user


@dataclass
class ScoringSett:
    user_id: int
    pattern: str
    active: bool = True
    score_change: int = 0
    id: ty.Optional[int] = None  # pylint: disable=redefined-builtin

    def __str__(self) -> str:
        return common.obj2str(self)

    def valid(self) -> bool:
        return bool(self.user_id and self.pattern and self.pattern.strip())

    @classmethod
    def from_row(cls, row: tyCursor) -> ScoringSett:
        return ScoringSett(
            id=row["scoring_sett__id"],
            user_id=row["scoring_sett__user_id"],
            pattern=row["scoring_sett__pattern"],
            active=row["scoring_sett__active"],
            score_change=row["scoring_sett__score_change"],
        )

    def to_row(self) -> common.Row:
        return {
            "scoring_sett__id": self.id,
            "scoring_sett__user_id": self.user_id,
            "scoring_sett__pattern": self.pattern,
            "scoring_sett__active": self.active,
            "scoring_sett__score_change": self.score_change,
        }


UserSources = ty.Dict[int, Source]
