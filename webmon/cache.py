#!/usr/bin/python3
"""
Cache storage functions.
"""

import os.path
import pathlib
import logging

import yaml

_LOG = logging.getLogger(__name__)


class Cache(object):
    """Cache for previous data"""
    def __init__(self, directory):
        _LOG.debug("Cache _directory: %s", directory)
        super(Cache, self).__init__()
        self._directory = directory
        # log cache files used in this session
        self._touched = set()

        # init
        if not os.path.isdir(self._directory):
            try:
                pathlib.Path(self._directory).mkdir(parents=True)
            except IOError as err:
                _LOG.debug("Cache: creating directory %s for cache error: %s",
                           self._directory, err)
                raise

    def get(self, oid):
        name = self._get_filename(oid)
        if os.path.isfile(name):
            try:
                with open(name) as fin:
                    return fin.read()
            except IOError as err:
                _LOG.error("Cache: load file %s from cache error: %s", name,
                           err)
        return None

    def get_meta(self, oid):
        """ Put metadata into cache. """
        name = self._get_filename_meta(oid)
        if os.path.isfile(name):
            try:
                with open(name) as fin:
                    return yaml.load(fin)
            except IOError as err:
                _LOG.error("Cache: load file %s from cache error: %s", name,
                           err)
        return None

    def put(self, oid, content):
        """ Put file into cache. """
        name = self._get_filename(oid)
        try:
            with open(name, "w") as fout:
                fout.write(content)
        except IOError as err:
            _LOG.error("Cache: error writing file %s into cache: %s", name,
                       err)

    def put_meta(self, oid, metadata):
        """ Put metadata into cache. """
        name = self._get_filename_meta(oid)
        try:
            if metadata:
                with open(name, "w") as fout:
                    yaml.dump(metadata, fout)
            else:
                if os.path.isfile(name):
                    os.unlink(name)
        except IOError as err:
            _LOG.error("Cache: error writing file %s into cache: %s", name,
                       err)

    def get_mtime(self, oid):
        """ Get modification time file in cache for `oid`. Return None when
        previous file not exist. """
        name = self._get_filename(oid)
        if not os.path.isfile(name):
            return None
        return os.path.getmtime(name)

    def update_mtime(self, oid):
        """ Update modification time file in cache by oid. """
        name = self._get_filename(oid)
        try:
            os.utime(name, None)
        except IOError as err:
            _LOG.error("Cache: change mtime for file %s error: %s", name, err)

    def _get_filename(self, oid):
        self._touched.add(oid)
        return os.path.join(self._directory, oid)

    def _get_filename_meta(self, oid):
        return os.path.join(self._directory, oid + ".meta")

    def delete_unused(self):
        """ Remove unused files from cache"""
        _LOG.info("cache.delete_unused; used=%d", len(self._touched))
        deleted = 0
        for fname in os.listdir(self._directory):
            fpath = os.path.join(self._directory, fname)
            foid = fname[:-5] if fname.endswith(".meta") else fname
            if os.path.isfile(fpath) and foid not in self._touched:
                try:
                    os.remove(fpath)
                    deleted += 1
                    _LOG.debug("cache: delete_unused %s", fpath)
                except IOError as err:
                    _LOG.error("delete file %s error: %s", fpath, err)
        _LOG.info("cache.delete_unused DONE; deleted: %d", deleted)
