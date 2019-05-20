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
import logging
import os
import typing as ty

import yaml

from . import model, database

_LOG = logging.getLogger(__name__)


def _load_sources(filename: str) -> ty.Optional[ty.List[ty.Any]]:
    """Load sources configuration from `filename`."""
    _LOG.debug("loading sources from %s", filename)
    if not os.path.isfile(filename):
        _LOG.error("loading sources file error: '%s' not found", filename)
        return None
    try:
        with open(filename) as fin:
            inps = [doc for doc in yaml.load_all(fin)
                    if doc and doc.get("enable", True)]
            _LOG.debug("loading sources - found %d enabled sources",
                       len(inps))
            if not inps:
                _LOG.error("loading sources error: no valid/enabled "
                           "sources found")
            return inps
    except IOError as err:
        _LOG.error("loading sources from file %s error: %s", filename,
                   err)
    except yaml.error.YAMLError as err:
        _LOG.error("loading sources from file %s - invalid YAML: %s",
                   filename, err)
    return None


def _migrate_url(inp) -> ty.Optional[model.Source]:
    source = model.Source()
    source.kind = 'url'
    source.name = inp.get('name', 'unknown')
    source.settings = {'url': inp['url']}
    source.interval = inp.get('interval')
    return source


def _migrate_rss(inp) -> ty.Optional[model.Source]:
    source = model.Source()
    source.kind = 'rss'
    source.name = inp.get('name', 'unknown')
    source.settings = {'url': inp['url']}
    source.interval = inp.get('interval')
    return source


def _migrate_jamendo(inp) -> ty.Optional[model.Source]:
    source = model.Source()
    source.kind = inp['kind']
    source.name = inp.get('name', 'unknown')
    source.settings = {'artist_id': inp['artist_id']}
    source.interval = inp.get('interval')
    return source


def _migrate_github(inp) -> ty.Optional[model.Source]:
    source = model.Source()
    source.kind = inp['kind']
    source.name = inp.get('name', 'unknown')
    source.settings = {
        'owner': inp['owner'],
        'repository': inp['repository'],
    }
    source.interval = inp.get('interval')
    return source


_MIGR_FUNCS = {
    'url': _migrate_url,
    'rss': _migrate_rss,
    'jamendo_albums': _migrate_jamendo,
    'jamendo_tracks': _migrate_jamendo,
    'github_commits': _migrate_github,
    'github_releases': _migrate_github,
    'github_tags': _migrate_github,
}


def migrate(filename):
    _LOG.info("migration %s start", filename)
    with database.DB.get() as db:
        users = list(database.users.get_all(db))
        if not users:
            _LOG.error("error migrating - no users")
            return
        user_id = users[0].id
        group_id = database.groups.get_all(db, user_id)[0].id

        for inp in _load_sources(filename):
            _LOG.info("migrating %r", inp)
            mfunc = _MIGR_FUNCS.get(inp.get('kind', 'url'))
            if mfunc:
                try:
                    source = mfunc(inp)
                except Exception as err:  # pylint: disable=broad-except
                    _LOG.exception("error migrating %r: %s", inp, err)
                    continue
                if not source:
                    _LOG.error("wrong source: %s", source)
                    continue
                source.filters = inp.get('filters')
                source.group_id = group_id
                source.user_id = user_id
                _LOG.info("new source: %s", source)
                database.sources.save(db, source)
        db.commit()

    _LOG.info("migration %s finished", filename)
