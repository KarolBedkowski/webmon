#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2019
#
# Distributed under terms of the GPLv3 license.

"""
Models
"""

import os
import hashlib
from datetime import datetime
import typing as ty
import logging

from webmon2 import common

_LOG = logging.getLogger(__name__)


class SourceGroup:
    __slots__ = (
        "id",
        "name",
        "user_id",
        "feed",
        "unread",
        "sources_count"
    )

    def __init__(self, **args):
        self.id = args.get('id')
        self.name = args.get('name')
        self.user_id = args.get('user_id')
        self.feed = args.get('feed', '')

        self.unread = args.get('unread')
        self.sources_count = args.get('sources_count')

    def __str__(self):
        return common.obj2str(self)

    def clone(self):
        sgr = SourceGroup()
        sgr.id = self.id
        sgr.name = self.name
        sgr.user_id = self.user_id
        sgr.feed = self.feed
        sgr.sources_count = self.sources_count
        return sgr


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
    )

    def __init__(self, **args):
        self.id = args.get('id')
        self.group_id = args.get('group_id')
        self.kind = args.get('kind')
        self.name = args.get('name')
        self.interval = args.get('interval')
        self.settings = args.get('settings')
        self.filters = args.get('filters')
        self.user_id = args.get('user_id')
        self.status = args.get('status')

        self.group = None
        self.state = None

        self.unread = None

    def __str__(self):
        return common.obj2str(self)

    def clone(self):
        src = Source()
        src.id = self.id
        src.group_id = self.group_id
        src.kind = self.kind
        src.name = self.name
        src.interval = self.interval
        src.settings = self.settings
        src.filters = self.filters
        src.user_id = self.user_id
        src.status = self.status
        return src


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
    )

    def __init__(self, **args):
        self.source_id = args.get('source_id')
        self.next_update = args.get('next_update')
        self.last_update = args.get('last_update')
        self.last_error = args.get('last_error')
        self.error_counter = args.get('error_counter')
        self.success_counter = args.get('success_counter')
        self.status = args.get('status')
        self.error = args.get('error')
        self.state = args.get('state')

    @staticmethod
    def new(source_id):
        source = SourceState()
        source.source_id = source_id
        source.next_update = datetime.now()
        source.error_counter = 0
        source.success_counter = 0
        source.status = 'new'
        return source

    def create_new(self):
        new_state = SourceState()
        new_state.source_id = self.source_id
        new_state.error_counter = self.error_counter
        new_state.success_counter = self.success_counter
        return new_state

    def new_ok(self):
        state = SourceState()
        state.source_id = self.source_id
        state.last_update = datetime.now()
        state.status = 'ok'
        state.success_counter = self.success_counter + 1
        state.last_error = None
        state.error = None
        state.error_counter = 0
        return state

    def new_error(self, error: str):
        state = SourceState()
        state.source_id = self.source_id
        state.error = error
        state.last_update = self.last_update
        state.status = 'error'
        state.success_counter = self.success_counter
        state.error_counter = self.error_counter + 1
        state.last_error = datetime.now()
        return state

    def new_not_modified(self):
        state = SourceState()
        state.source_id = self.source_id
        state.last_update = datetime.now()
        state.status = 'not modified'
        state.last_error = None
        state.error = None
        state.error_counter = 0
        state.success_counter = self.success_counter + 1
        return state

    def set_state(self, key, value):
        if self.state is None:
            self.state = {}
        self.state[key] = value

    def get_state(self, key, default=None):
        return self.state.get(key, default) if self.state else default

    def __str__(self):
        return common.obj2str(self)


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
        "user_id",
        "source",
    )

    def __init__(self, id_=None, source_id=None):
        self.id = id_   # type: ty.Optional[int]
        self.source_id = source_id  # type: ty.Optional[int]
        self.updated = None  # type: ty.Optional[datetime]
        self.created = None  # type: ty.Optional[datetime]
        self.read_mark = 0  # type: int
        self.star_mark = 0  # type: int
        self.status = None  # type: ty.Optional[str]
        self.oid = None     # type: ty.Optional[str]
        self.title = None   # type: ty.Optional[str]
        self.url = None     # type: ty.Optional[str]
        self.content = None  # type: ty.Optional[str]
        self.opts = None    # type: ty.Optional[ty.Dict[str, ty.Any]]
        self.user_id = None  # type: ty.Optional[int]

        self.source = None  # type: ty.Optional[Source]

    def __str__(self):
        return common.obj2str(self)

    def clone(self):
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
        return entry

    @staticmethod
    def for_source(source: Source):
        entry = Entry(source_id=source.id)
        entry.user_id = source.user_id
        return entry

    def calculate_oid(self):
        data = "".join(map(
            str, (self.source_id, self.title, self.url, self.content)))
        csum = hashlib.sha1(data.encode('utf-8'))
        self.oid = csum.hexdigest()
        return self.oid

    def get_opt(self, key, default=None):
        return self.opts.get(key, default) if self.opts else default

    def set_opt(self, key, value):
        if self.opts is None:
            self.opts = {}
        self.opts[key] = value

    def human_title(self):
        if self.title:
            return self.title
        if len(self.content) > 50:
            return self.content[:50] + '…'
        return self.content

    def is_long_content(self) -> bool:
        if not self.content:
            return False
        lines = self.content.count('\n')
        return lines > 20

    def get_summary(self):
        return '\n'.join(self.content.split('\n', 21)[:20]) + "\n…"

    def validate(self):
        if not isinstance(self.updated, datetime):
            _LOG.error("wrong entry.updated:  %r (%s)", self.updated, self)
        if not isinstance(self.created, datetime):
            _LOG.error("wrong entry.created:  %r (%s)", self.created, self)
        if not self.title:
            _LOG.error("missing title %s", self)


Entries = ty.Iterable[Entry]


class Setting:
    __slots__ = (
        "key",
        "value",
        "value_type",
        "description",
        "user_id",
    )

    def __init__(self, key=None, value=None, value_type=None,
                 description=None, user_id=None):
        self.key = key
        self.value = value
        self.value_type = value_type
        self.description = description
        self.user_id = user_id

    def set_value(self, value):
        if self.value_type == 'int':
            self.value = int(value)
        elif self.value_type == 'float':
            self.value = float(value)
        elif self.value_type == 'bool':
            self.value = value.lower() in ('true', 'yes')
        else:
            self.value = str(value)

    def __str__(self):
        return common.obj2str(self)


class User:
    __slots__ = (
        "id",
        "login",
        "email",
        "password",
        "active",
        "admin",
    )

    def __init__(self, **args):
        self.id = args.get('id')
        self.login = args.get('login')
        self.email = args.get('email')
        self.password = args.get('password')
        self.active = args.get('active')
        self.admin = args.get('admin')

    def hash_password(self, password):
        salt = os.urandom(16)
        phash = hashlib.scrypt(
            password.encode('utf-8'), salt=salt, n=16, r=16, p=2)
        self.password = salt.hex() + phash.hex()

    def verify_password(self, password):
        salt = bytes.fromhex(self.password[:32])
        passw = bytes.fromhex(self.password[32:])
        phash = hashlib.scrypt(
            password.encode('utf-8'), salt=salt, n=16, r=16, p=2)
        return passw == phash
