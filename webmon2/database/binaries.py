#!/usr/bin/python3
"""

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""
import logging

import psycopg2

_LOG = logging.getLogger(__name__)


def get(db, datahash: str, user_id: int):
    if not datahash:
        return None
    with db.cursor() as cur:
        cur.execute("select data, content_type from binaries "
                    "where datahash=%s and user_id=%s",
                    (datahash, user_id))
        row = cur.fetchone()
        return row


def save(db, user_id: int, content_type: str, datahash: str, data):
    _LOG.debug("save binary: %r, %r, %r, %s", user_id, content_type,
               datahash, type(data))
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO binaries (datahash, user_id, data, content_type) "
            "VALUES (%s, %s, %s, %s) "
            "ON conflict (datahash, user_id) DO NOTHING",
            (datahash, user_id, psycopg2.Binary(data), content_type))
