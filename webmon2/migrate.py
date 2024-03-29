#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Migration utils
"""
import argparse
import logging
import os
import typing as ty

import yaml

from . import database, model

_LOG = logging.getLogger(__name__)


def _load_sources(filename: str) -> ty.Optional[ty.List[ty.Any]]:
    """Load sources configuration from `filename`."""
    _LOG.debug("loading sources from %s", filename)
    if not os.path.isfile(filename):
        _LOG.error("loading sources file error: '%s' not found", filename)
        return None

    try:
        with open(filename, encoding="UTF-8") as fin:
            inps = [
                doc
                for doc in yaml.load_all(fin, Loader=None)
                if doc and doc.get("enable", True)
            ]
            _LOG.debug("loading sources - found %d enabled sources", len(inps))
            if not inps:
                _LOG.error(
                    "loading sources error: no valid/enabled sources found"
                    "file: %s",
                    filename,
                )

            return inps

    except IOError as err:
        _LOG.error("loading sources from file %s error: %s", filename, err)
    except yaml.error.YAMLError as err:
        _LOG.error(
            "loading sources from file %s - invalid YAML: %s", filename, err
        )

    return None


def _migrate_url(inp: model.ConfDict) -> ty.Optional[model.Source]:
    source = model.Source(
        kind="url",
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {"url": inp["url"]}
    source.interval = inp.get("interval")
    return source


def _migrate_rss(inp: model.ConfDict) -> ty.Optional[model.Source]:
    source = model.Source(
        kind="rss",
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {"url": inp["url"]}
    source.interval = inp.get("interval")
    return source


def _migrate_jamendo(inp: model.ConfDict) -> ty.Optional[model.Source]:
    source = model.Source(
        kind=inp["kind"],
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {"artist_id": inp["artist_id"]}
    source.interval = inp.get("interval")
    return source


def _migrate_github(inp: model.ConfDict) -> ty.Optional[model.Source]:
    source = model.Source(
        kind=inp["kind"],
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {
        "owner": inp["owner"],
        "repository": inp["repository"],
    }
    source.interval = inp.get("interval")
    return source


_MIGR_FUNCS = {
    "url": _migrate_url,
    "rss": _migrate_rss,
    "jamendo_albums": _migrate_jamendo,
    "jamendo_tracks": _migrate_jamendo,
    "github_commits": _migrate_github,
    "github_releases": _migrate_github,
    "github_tags": _migrate_github,
}


def migrate(args: argparse.Namespace) -> None:
    filename = args.migrate_filename
    user_login = args.migrate_user
    _LOG.info("migration from %s to user %s start", filename, user_login)
    with database.DB.get() as db:
        try:
            user = database.users.get(db, login=user_login)
        except database.NotFound:
            _LOG.error(
                "error migrating - users %s not found in database", user_login
            )
            return

        user_id = user.id
        assert user_id
        group_id = database.groups.get_all(db, user_id)[0].id
        assert group_id

        _LOG.debug("migrate to user_id: %d group: %d", user_id, group_id)

        for inp in _load_sources(filename) or []:
            _LOG.info("migrating %r", inp)
            mfunc = _MIGR_FUNCS.get(inp.get("kind", "url"))
            if mfunc:
                try:
                    source = mfunc(inp)
                except Exception as err:  # pylint: disable=broad-except
                    _LOG.exception("error migrating %r: %s", inp, err)
                    continue

                if not source:
                    _LOG.error("wrong source: %s", source)
                    continue

                source.filters = inp.get("filters")
                source.group_id = group_id
                source.user_id = user_id
                _LOG.info("new source: %r", source)
                database.sources.save(db, source)

        db.commit()

    _LOG.info("migration %s finished", filename)
