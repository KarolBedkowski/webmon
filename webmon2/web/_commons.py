#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Common gui api functions
"""
import math
import secrets
import typing as ty

from flask import g, session

from webmon2 import model
from webmon2.database import DB

PAGE_LIMIT = 25


def preprate_entries_list(
    entries: ty.List[model.Entry], page: int, total_entries: int, order: str
) -> ty.Dict[str, ty.Any]:
    last_page = math.ceil(total_entries / PAGE_LIMIT) - 1
    info = {
        "min_id": min(entry.id for entry in entries) if entries else None,
        "max_id": max(entry.id for entry in entries) if entries else None,
        "more": page is not None and (page + 1) * PAGE_LIMIT < total_entries,
        "entries": entries,
        "next_page": (
            min(page + 1, int(total_entries / PAGE_LIMIT))
            if page is not None
            else None
        ),
        "prev_page": (max(0, page - 1) if page is not None else None),
        "total_entries": total_entries,
        "page": min(page, last_page),
        "last_page": last_page,
        "order": order,
    }
    return info


def get_db() -> DB:
    database: ty.Optional[DB] = getattr(g, "db", None)
    if database is None:
        database = g.db = DB.get()

    return database


def generate_csrf_token() -> None:
    """
    Generate new random csrf token and store it in session.
    """
    session["_csrf_token"] = secrets.token_urlsafe(16)
    session.modified = True
