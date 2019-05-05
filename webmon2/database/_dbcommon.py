#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Common functions for db access
"""

import typing as ty

import json

from webmon2 import model


class NotFound(Exception):
    pass


def get_json_if_exists(row_keys, key, row, default=None):
    if key not in row_keys:
        return default
    value = row[key]
    return json.loads(value) if value else default


def entry_from_row(row) -> model.Entry:
    entry = model.Entry(row["entry_id"])
    entry.source_id = row["entry_source_id"]
    entry.updated = row["entry_updated"]
    entry.created = row["entry_created"]
    entry.read_mark = row["entry_read_mark"]
    entry.star_mark = row["entry_star_mark"]
    entry.status = row["entry_status"]
    entry.oid = row["entry_oid"]
    entry.title = row["entry_title"]
    entry.url = row["entry_url"]
    row_keys = row.keys()
    entry.opts = get_json_if_exists(row_keys, "entry_opts", row)
    if "entry_content" in row_keys:
        entry.content = row["entry_content"]
    entry.user_id = row['entry_user_id']
    return entry


def entry_to_row(entry: model.Entry) -> ty.Dict[str, ty.Any]:
    return {
        'source_id': entry.source_id,
        'updated': entry.updated,
        'created': entry.created,
        'read_mark': entry.read_mark,
        'star_mark': entry.star_mark,
        'status': entry.status,
        'oid': entry.oid,
        'title': entry.title,
        'url': entry.url,
        'opts': json.dumps(entry.opts),
        'content': entry.content,
        'id': entry.id,
        'user_id': entry.user_id,
    }


def source_from_row(row) -> model.Source:
    source = model.Source()
    source.id = row["source_id"]
    source.group_id = row["source_group_id"]
    source.kind = row["source_kind"]
    source.name = row["source_name"]
    source.interval = row["source_interval"]
    row_keys = row.keys()
    source.settings = get_json_if_exists(row_keys, "source_settings", row)
    source.filters = get_json_if_exists(row_keys, "source_filters", row)
    source.user_id = row['source_user_id']
    return source


def source_group_from_row(row):
    return model.SourceGroup(row["source_group_id"],
                             row["source_group_name"],
                             row["source_group_user_id"],
                             row["source_group_feed"])


def source_to_row(source: model.Source):
    return {
        'group_id': source.group_id,
        'kind': source.kind,
        'name': source.name,
        'interval': source.interval,
        'settings': json.dumps(source.settings) if source.settings else None,
        'filters': json.dumps(source.filters) if source.filters else None,
        'user_id': source.user_id,
        'id': source.id,
    }
