#!/usr/bin/python3
"""
Cache storage functions.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""
# TODO: logowanie przez context?

import hashlib
import logging
import os.path
import pathlib
import time

import yaml

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

_LOG = logging.getLogger("cache")


def _get_content(fname: str) -> str:
    if os.path.isfile(fname):
        try:
            with open(fname) as fin:
                return fin.read()
        except IOError as err:
            _LOG.error("load file %s from cache error: %s", fname, err)
    return None


def _get_meta(fname: str) -> str:
    if os.path.isfile(fname):
        try:
            with open(fname) as fin:
                return yaml.load(fin)
        except IOError as err:
            _LOG.error("load meta file %s from cache error: %s", fname, err)
        except yaml.error.YAMLError as err:
            _LOG.error("load meta file %s from cache error - broken YAML: %s",
                       fname, err)
    return None


class Cache(object):
    """Cache for previous data."""

    def __init__(self, directory: str) -> None:
        """
        Constructor.

        :param directory: path to cache in local filesystem
        """
        _LOG.debug("init; directory: %s", directory)
        super(Cache, self).__init__()
        self._directory = directory
        # log cache files used in this session
        self._touched = set()  # type: Set[str]

        # init
        common.create_missing_dir(self._directory)

    def get(self, oid: str):
        """Get file from cache by `oid`."""
        name = self._get_filename(oid)
        content = _get_content(name)
        _LOG.debug("get %r, content_len=%d", oid, len(content or ''))
        return content

    def get_meta(self, oid: str):
        """Get metadata from cache for file by `oid`."""
        name = self._get_filename_meta(oid)
        meta = _get_meta(name)
        _LOG.debug("get_meta %r: meta=%r", oid, meta)
        return meta

    def put(self, oid: str, content: str):
        """Put `content` into cache as temp file identified by `oid`."""
        content = content or ''
        _LOG.debug("put %r, content_len=%d", oid, len(content))
        name = self._get_filename(oid)
        try:
            with open(name, "w") as fout:
                fout.write(content)
        except IOError as err:
            _LOG.error("error writing file %s into cache: %s", name, err)

    def put_meta(self, oid: str, metadata: dict):
        """Put `metadata` into cache identified by `oid`."""
        _LOG.debug("put_meta %r", oid)
        name = self._get_filename_meta(oid)
        try:
            if metadata:
                with open(name, "w") as fout:
                    yaml.dump(metadata, fout)
            else:
                if os.path.isfile(name):
                    os.unlink(name)
        except (IOError, yaml.error.YAMLError) as err:
            _LOG.error("error writing file %s into cache: %s", name, err)

    def get_mtime(self, oid: str):
        """Get modification time of cached file identified by `oid`.

        Return None when previous file not exist.
        """
        name = self._get_filename(oid)
        if not os.path.isfile(name):
            _LOG.debug("get_mtime %r - file not found", oid)
            return None
        mtime = os.path.getmtime(name)
        _LOG.debug("get_mtime %r - ts: %s", oid, mtime)
        return mtime

    def _get_filename(self, oid: str):
        self._touched.add(oid)
        return os.path.join(self._directory, oid)

    def _get_filename_meta(self, oid: str):
        return os.path.join(self._directory, oid + ".meta")
