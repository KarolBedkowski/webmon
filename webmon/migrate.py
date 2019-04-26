#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Migration utils
"""
import logging
import os
import typing as ty

import yaml

from . import model, db

_LOG = logging.getLogger(__file__)


def _load_inputs(filename: str) -> ty.Optional[ty.List[ty.Any]]:
    """Load inputs configuration from `filename`."""
    _LOG.debug("loading inputs from %s", filename)
    if not os.path.isfile(filename):
        _LOG.error("loading inputs file error: '%s' not found", filename)
        return None
    try:
        with open(filename) as fin:
            inps = [doc for doc in yaml.load_all(fin)
                    if doc and doc.get("enable", True)]
            _LOG.debug("loading inputs - found %d enabled inputs",
                       len(inps))
            if not inps:
                _LOG.error("loading inputs error: no valid/enabled "
                           "inputs found")
            return inps
    except IOError as err:
        _LOG.error("loading inputs from file %s error: %s", filename,
                   err)
    except yaml.error.YAMLError as err:
        _LOG.error("loading inputs from file %s - invalid YAML: %s",
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
    database = db.DB.get()
    for inp in _load_inputs(filename):
        _LOG.info("migrating %r", inp)
        mfunc = _MIGR_FUNCS.get(inp.get('kind', 'url'))
        if mfunc:
            try:
                source = mfunc(inp)
            except Exception as err:
                _LOG.exception("error migrating %r: %s", inp, err)
                continue
            if not source:
                _LOG.error("wrong source: %s", source)
                continue
            source.filters = inp.get('filters')
            _LOG.info("new source: %s", source)
            database.save_source(source)
    database.close()

    _LOG.info("migration %s finished", filename)