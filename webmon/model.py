#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019  <@K-HP>
#
# Distributed under terms of the GPLv3 license.

"""

"""

import hashlib
import datetime
import typing as ty


def _val2str(value):
    value = str(value)
    if len(value) > 64:
        return value[:64] + "..."
    return value


def obj2str(obj):
    kvs = ", ".join([key + "=" + _val2str(val)
                     for key, val in obj.__dict__.items()
                     if key[0] != "_"])
    return "<" + obj.__class__.__name__ + " " + kvs + ">"


class SourceGroup:
    def __init__(self, id_=None, name=None):
        self.id = id_
        self.name = name

    def clone(self):
        sg = SourceGroup()
        sg.id = self.id
        sg.name = self.name
        return sg


class Source:
    def __init__(self):
        self.id = None
        self.group_id = None
        self.kind = None
        self.name = None
        self.interval = None
        self.settings = None
        self.filters = None

        self.group = None
        self.state = None

        self.unread = None

    def __str__(self):
        return obj2str(self)

    def clone(self):
        src = Source()
        src.id = self.id
        src.group_id = self.group_id
        src.kind = self.kind
        src.name = self.name
        src.interval = self.interval
        src.settings = self.settings
        src.filters = self.filters
        return src


class SourceState:
    def __init__(self):
        self.source_id = None
        self.next_update = None
        self.last_update = None
        self.last_error = None
        self.error_counter = None
        self.success_counter = None
        self.status = None
        self.error = None
        self.state = None

    @staticmethod
    def new(source_id):
        source = SourceState()
        source.source_id = source_id
        source.next_update = datetime.datetime.now()
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
        state.last_update = datetime.datetime.now()
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
        return state

    def new_not_modified(self):
        state = SourceState()
        state.source_id = self.source_id
        state.last_update = datetime.datetime.now()
        state.status = 'not modified'
        state.last_error = None
        state.error = None
        state.error_counter = 0
        state.success_counter = self.success_counter + 1
        return state

    def set_state(self, key, value):
        if self.state is None:
            self.state = {}
        curr_val = self.state.get(key)
        self.state[key] = value

    def get_state(self, key, default=None):
        return self.state.get(key, default) if self.state else default

    def __str__(self):
        return obj2str(self)


class Entry:
    def __init__(self, id_=None, source_id=None):
        self.id = id_
        self.source_id = source_id
        self.updated = None
        self.created = None
        self.read_mark = 0
        self.star_mark = 0
        self.status = None
        self.oid = None
        self.title = None
        self.url = None
        self.content = None
        self.opts = None

        self.source = None

    def __str__(self):
        return obj2str(self)

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
        return entry

    @staticmethod
    def for_source(source: Source):
        entry = Entry(source_id=source.id)
        return entry

    def calculate_oid(self):
        csum = hashlib.sha1()
        for val in (self.source_id, self.title, self.url, self.content):
            csum.update(str(val).encode("utf-8"))
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
            return self.content[:50] + '...'
        return self.content


Entries = ty.Iterable[Entry]


class Setting:
    def __init__(self, key=None, value=None, value_type=None,
                 description=None):
        self.key = key
        self.value = value
        self.value_type = value_type
        self.description = description

    def set_value(self, value):
        if self.value_type == 'int':
            self.value = int(value)
        elif self.value_type == 'float':
            self.value = float(value)
        else:
            self.value = str(value)

    def __str__(self):
        return obj2str(self)
