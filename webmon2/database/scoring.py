#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2021
#
# Distributed under terms of the GPLv3 license.

"""
Access & manage users in db
"""
import logging
import typing as ty

from webmon2 import model

from ._db import DB

_LOG = logging.getLogger(__name__)


class LoginAlreadyExistsError(Exception):
    pass


_GET_ALL_SQL_FOR_USER = """
select id as scoring_sett__id, user_id as scoring_sett__user_id,
    pattern as scoring_sett__pattern, active as scoring_sett__active,
    score_change as scoring_sett__score_change
from scoring_sett
where user_id = %s
"""


def get(db: DB, user_id: int) -> ty.Iterable[model.ScoringSett]:
    """Get scoring settings for user"""
    with db.cursor() as cur:
        cur.execute(_GET_ALL_SQL_FOR_USER, (user_id,))
        return [model.ScoringSett.from_row(row) for row in cur]


_GET_ACTIVE_SQL_FOR_USER = (
    _GET_ALL_SQL_FOR_USER
    + """
and active
"""
)


def get_active(db: DB, user_id: int) -> ty.Iterable[model.ScoringSett]:
    """Get active scoring settings for user"""
    with db.cursor() as cur:
        cur.execute(_GET_ACTIVE_SQL_FOR_USER, (user_id,))
        return [model.ScoringSett.from_row(row) for row in cur]


_INSERT_SQL = """
insert into scoring_sett (user_id, pattern, active, score_change)
values (%(scoring_sett__user_id)s, %(scoring_sett__pattern)s,
    %(scoring_sett__active)s, %(scoring_sett__score_change)s)
"""


def save(
    db: DB, user_id: int, scoring_settings: ty.Iterable[model.ScoringSett]
) -> None:
    """Save / update scoring settings for user"""
    with db.cursor() as cur:
        cur.execute("delete from scoring_sett where user_id=%s", (user_id,))
        if scoring_settings:
            rows = [scs.to_row() for scs in scoring_settings]
            cur.executemany(_INSERT_SQL, rows)
