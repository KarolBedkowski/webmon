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
SELECT id AS scoring_sett__id, user_id AS scoring_sett__user_id,
    pattern AS scoring_sett__pattern, active AS scoring_sett__active,
    score_change AS scoring_sett__score_change
FROM scoring_sett
WHERE user_id = %s
"""


def get(db: DB, user_id: int) -> ty.List[model.ScoringSett]:
    """Get scoring settings for user"""
    with db.cursor() as cur:
        cur.execute(_GET_ALL_SQL_FOR_USER, (user_id,))
        return [model.ScoringSett.from_row(row) for row in cur]


def get_active(db: DB, user_id: int) -> ty.List[model.ScoringSett]:
    """Get active scoring settings for user"""
    sql = _GET_ALL_SQL_FOR_USER + " AND active"
    with db.cursor() as cur:
        cur.execute(sql, (user_id,))
        return [model.ScoringSett.from_row(row) for row in cur]


_INSERT_SQL = """
INSERT INTO scoring_sett (user_id, pattern, active, score_change)
VALUES (%(scoring_sett__user_id)s, %(scoring_sett__pattern)s,
    %(scoring_sett__active)s, %(scoring_sett__score_change)s)
"""


def save(
    db: DB, user_id: int, scoring_settings: ty.Iterable[model.ScoringSett]
) -> None:
    """Save / update scoring settings for user"""
    with db.cursor() as cur:
        cur.execute("DELETE FROM scoring_sett WHERE user_id=%s", (user_id,))
        if scoring_settings:
            rows = [scs.to_row() for scs in scoring_settings]
            cur.executemany(_INSERT_SQL, rows)
