#!/usr/bin/python3

import os.path


class Cache(object):
    """Cache for previous data"""
    def __init__(self, directory):
        super(Cache, self).__init__()
        self.directory = directory

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
        name = self._get_filename(oid)
        if not os.path.isfile(name):
            return None
        return os.path.getmtime(name)

    def update_mtime(self, oid):
        name = self._get_filename(oid)
        os.utime(name, None)

    def _get_filename(self, oid):
        return os.path.join(self.directory, oid)
