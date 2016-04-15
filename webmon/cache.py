#!/usr/bin/python3
"""
Cache storage functions.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import os.path
import logging
import pathlib

import yaml

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

_LOG = logging.getLogger("cache")
_TEMP_EXT = ".tmp"


def _get_content(fname):
    if os.path.isfile(fname):
        try:
            with open(fname) as fin:
                return fin.read()
        except IOError as err:
            _LOG.error("load file %s from cache error: %s", fname, err)
        except yaml.error.YAMLError as err:
            _LOG.error("load meta file %s from cache error - broken YAML: %s",
                       fname, err)
    return None


def _get_meta(fname):
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

    def __init__(self, directory):
        """
        Constructor.

        :param directory: path to cache in local filesystem
        """
        _LOG.debug("init; directory: %s", directory)
        super(Cache, self).__init__()
        self._directory = directory
        # log cache files used in this session
        self._touched = set()

        # init
        if not os.path.isdir(self._directory):
            try:
                pathlib.Path(self._directory).mkdir(parents=True)
            except IOError as err:
                _LOG.error("creating directory %s for cache error: %s",
                           self._directory, err)
                raise

    def get(self, oid):
        """Get file from cache by `oid`."""
        name = self._get_filename(oid)
        content = _get_content(name)
        _LOG.debug("get %r, content_len=%d", oid, len(content or ''))
        return content

    def get_meta(self, oid):
        """Get metadata from cache for file by `oid`."""
        name = self._get_filename_meta(oid)
        meta = _get_meta(name)
        _LOG.debug("get_meta %r: meta=%r", oid, meta)
        return meta

    def get_recovered(self, oid):
        """Find temp files for `oid` and return content, mtime and meta.

        Temp files contains new loaded content are renamed when application end
        without errors.
        """
        name = self._get_filename(oid) + _TEMP_EXT
        if not os.path.isfile(name):
            _LOG.debug("get_recovered %r - not found", oid)
            return None, None, None

        content, mtime, meta = None, None, None
        mtime = os.path.getmtime(name)
        content = _get_content(name)
        meta_name = self._get_filename_meta(oid) + _TEMP_EXT
        meta = _get_meta(meta_name)

        _LOG.debug("get_recovered %r: mtime=%s, content_len=%d, meta=%r",
                   oid, mtime, len(content or ''), meta)
        return content, mtime, meta

    def put(self, oid, content):
        """Put `content` into cache as temp file identified by `oid`."""
        content = content or ''
        _LOG.debug("put %r, content_len=%d", oid, len(content))
        name = self._get_filename(oid) + _TEMP_EXT
        try:
            with open(name, "w") as fout:
                fout.write(content)
        except IOError as err:
            _LOG.error("error writing file %s into cache: %s", name, err)

    def put_meta(self, oid, metadata):
        """Put `metadata` into cache identified by `oid`."""
        _LOG.debug("put_meta %r", oid)
        name = self._get_filename_meta(oid) + _TEMP_EXT
        try:
            if metadata:
                with open(name, "w") as fout:
                    yaml.dump(metadata, fout)
            else:
                if os.path.isfile(name):
                    os.unlink(name)
        except (IOError, yaml.error.YAMLError) as err:
            _LOG.error("error writing file %s into cache: %s", name, err)

    def get_mtime(self, oid):
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

    def commmit_temps(self, delete_not_used=False):
        """Commit new files into cache.

        Delete non-tmp and not-touched files from cached.
        Rename tmp-files.
        """
        # delete old file
        if delete_not_used:
            for fname in os.listdir(self._directory):
                fpath = os.path.join(self._directory, fname)
                if fname.endswith(_TEMP_EXT) or \
                        os.path.splitext(fname)[0] in self._touched or \
                        not os.path.isfile(fpath):
                    continue
                _LOG.debug("commmit_temps - delete: '%s'", fpath)
                try:
                    os.remove(fpath)
                except IOError as err:
                    _LOG.error("delete unused file %s error: %s", fpath, err)

        # rename temp file
        for fname in os.listdir(self._directory):
            fpath = os.path.join(self._directory, fname)
            if not fname.endswith(_TEMP_EXT) or not os.path.isfile(fpath):
                continue
            dst_fpath = fpath[:-4]
            try:
                _LOG.debug("commmit_temps - rename: '%s' -> '%s'", fpath,
                           dst_fpath)
                os.rename(fpath, dst_fpath)
            except IOError as err:
                _LOG.error("rename temp file %s error: %s", fpath, err)

    def _get_filename(self, oid):
        self._touched.add(oid)
        return os.path.join(self._directory, oid)

    def _get_filename_meta(self, oid):
        return os.path.join(self._directory, oid + ".meta")
