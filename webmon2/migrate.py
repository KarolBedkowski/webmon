# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Migration utils
"""
from __future__ import annotations

import typing as ty
from pathlib import Path

import structlog
import yaml

from . import database, model

if ty.TYPE_CHECKING:
    import argparse

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)


def _load_sources(filename: str) -> list[ty.Any] | None:
    """Load sources configuration from `filename`."""
    sfile = Path(filename)
    if not sfile.is_file():
        _LOG.error(
            "migrate: load sources from %r error - file not found", filename
        )
        return None

    _LOG.debug("migrate: loading sources from %s", filename)
    try:
        with sfile.open(encoding="UTF-8") as fin:
            inps = [
                doc
                for doc in yaml.load_all(fin, Loader=yaml.Loader)
                if doc and doc.get("enable", True)
            ]
            _LOG.debug("migrate: found %d enabled sources", len(inps))

            return inps

    except OSError as err:
        _LOG.error(
            "migrate: loading source from file %s error", filename, error=err
        )

    except yaml.error.YAMLError as err:
        _LOG.error(
            "migrate: loading source from file %s error: invalid YAML",
            filename,
            error=err,
        )

    return None


def _migrate_url(inp: model.ConfDict) -> model.Source | None:
    source = model.Source(
        kind="url",
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {"url": inp["url"]}
    source.interval = inp.get("interval")
    return source


def _migrate_rss(inp: model.ConfDict) -> model.Source | None:
    source = model.Source(
        kind="rss",
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {"url": inp["url"]}
    source.interval = inp.get("interval")
    return source


def _migrate_jamendo(inp: model.ConfDict) -> model.Source | None:
    source = model.Source(
        kind=inp["kind"],
        name=inp.get("name", "unknown"),
        user_id=0,
        group_id=0,
    )
    source.settings = {"artist_id": inp["artist_id"]}
    source.interval = inp.get("interval")
    return source


def _migrate_github(inp: model.ConfDict) -> model.Source | None:
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
    _LOG.info("migrate: from %s to user %s start", filename, user_login)
    with database.DB.get() as db:
        try:
            user = database.users.get(db, login=user_login)
        except database.NotFound:
            _LOG.error(
                "migrate: error: users %r not found in database", user_login
            )
            return

        user_id = user.id
        assert user_id
        group_id = database.groups.get_all(db, user_id)[0].id
        assert group_id

        _LOG.debug("migrate: starting", user_id=user_id, group_id=group_id)

        for inp in _load_sources(filename) or []:
            _LOG.info("migrate: loading %r", inp)
            mfunc = _MIGR_FUNCS.get(inp.get("kind", "url"))
            if mfunc:
                try:
                    source = mfunc(inp)
                except Exception as err:  # pylint: disable=broad-except
                    _LOG.exception(
                        "migrate: error migrating %r", inp, error=err
                    )
                    continue

                if not source:
                    _LOG.error("migrate: wrong source: %s", source)
                    continue

                source.filters = inp.get("filters")
                source.group_id = group_id
                source.user_id = user_id
                _LOG.info("migrate: new source: %r", source)
                database.sources.save(db, source)

        db.commit()

    _LOG.info("migrate: load %s finished", filename)
