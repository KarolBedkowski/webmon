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
    """Cache for previous data"""
    def __init__(self, directory):
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
        _LOG.debug("get %r", oid)
        name = self._get_filename(oid)
        return _get_content(name)

    def get_meta(self, oid):
        """ Put metadata into cache. """
        _LOG.debug("get_meta %r", oid)
        name = self._get_filename_meta(oid)
        return _get_meta(name)

    def get_recovered(self, oid):
        """Find temp files for `oid` and return content, mtime and meta.
        Temp files contains new loaded content are renamed when application end
        without errors."""
        _LOG.debug("get_recovered %r", oid)
        name = self._get_filename(oid) + _TEMP_EXT
        content, mtime, meta = None, None, None
        if os.path.isfile(name):
            mtime = os.path.getmtime(name)
            content = _get_content(name)

        meta_name = self._get_filename_meta(oid) + _TEMP_EXT
        meta = _get_meta(meta_name)
        return content, mtime, meta

    def put(self, oid, content):
        """ Put file into cache as temp file. """
        _LOG.debug("put %r", oid)
        name = self._get_filename(oid) + _TEMP_EXT
        try:
            with open(name, "w") as fout:
                fout.write(content)
        except IOError as err:
            _LOG.error("error writing file %s into cache: %s", name, err)

    def put_meta(self, oid, metadata):
        """ Put metadata into cache. """
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
        """ Get modification time file in cache for `oid`. Return None when
        previous file not exist. """
        _LOG.debug("get_mtime %r", oid)
        name = self._get_filename(oid)
        if not os.path.isfile(name):
            return None
        return os.path.getmtime(name)

    def commmit_temps(self):
        """Commit new files into cache."""
        # delete old file
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
