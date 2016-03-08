#!/usr/bin/python3

import os.path
import pathlib
import logging

_LOG = logging.getLogger(__name__)


class Cache(object):
    """Cache for previous data"""
    def __init__(self, directory):
        super(Cache, self).__init__()
        self.directory = directory
        # log cache files used in this session
        self._touched = set()
        if not os.path.isdir(self.directory):
            pathlib.Path(self.directory).mkdir(parents=True)

    def get(self, oid):
        name = self._get_filename(oid)
        try:
            with open(name) as fin:
                return fin.read()
        except IOError:
            pass
        return

    def put(self, oid, content):
        name = self._get_filename(oid)
        with open(name, "w") as fout:
            fout.write(content)

    def get_mtime(self, oid):
        self._touched.add(oid)
        name = self._get_filename(oid)
        if not os.path.isfile(name):
            return None
        return os.path.getmtime(name)

    def update_mtime(self, oid):
        name = self._get_filename(oid)
        os.utime(name, None)

    def _get_filename(self, oid):
        return os.path.join(self.directory, oid)

    def delete_unused(self):
        """ Remove unused files from cache"""
        _LOG.info("cache.delete_unused; used=%d", len(self._touched))
        deleted = 0
        for fname in os.listdir(self.directory):
            fpath = os.path.join(self.directory, fname)
            if os.path.isfile(fpath) and fname not in self._touched:
                try:
                    os.remove(fpath)
                    deleted += 1
                    _LOG.debug("cache: delete_unused %s", fpath)
                except IOError as err:
                    _LOG.error("delete file %s error: %s", fpath, err)
        _LOG.info("cache.delete_unused DONE; deleted: %d", deleted)
