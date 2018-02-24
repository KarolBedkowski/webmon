#!/usr/bin/python3
"""
Configuration related functions.

Copyright (c) Karol Będkowski, 2016-2018

This file is part of webmon.
Licence: GPLv2+
"""

import hashlib
import logging
import os
import os.path
from contextlib import contextmanager

try:
    import fcntl
except ImportError:
    fcntl = None

import yaml

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2018"

_LOG = logging.getLogger("conf")


def load_configuration(filename: str) -> dict:
    """Load app configuration from `filename`."""
    if not filename:
        filename = _find_config_file("config.yaml")

    _LOG.debug("loading configuration from %s", filename)
    if not filename or not os.path.isfile(filename):
        _LOG.error("loading configuration file error: '%s' not found",
                   filename)
        return None
    try:
        with open(filename) as fin:
            conf = yaml.load(fin)
            if not conf:
                _LOG.error("missing configuration")
            return conf
    except IOError as err:
        _LOG.error("loading configuration from file %s error: %s", filename,
                   err)
    except yaml.error.YAMLError as err:
        _LOG.error("loading configuration from file %s - invalid YAML: %s",
                   filename, err)
    return None


def load_inputs(filename: str) -> list:
    """Load inputs configuration from `filename`."""
    if not filename:
        filename = _find_config_file("inputs.yaml")

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


def _find_config_file(name: str, must_exists: bool=True) -> str:
    if os.path.isfile(name):
        return name
    # try ~/.config/webmon/
    bname = os.path.basename(name)
    fpath = os.path.expanduser(os.path.join("~", ".config", "webmon", bname))
    return fpath if not must_exists or os.path.isfile(fpath) else name


def gen_input_oid(conf: dict) -> str:
    """Generate object id according to configuration."""
    oid = conf.get('oid') or conf.get('id')
    if oid:
        return oid
    csum = hashlib.sha1()
    for keyval in _conf2string(conf):
        csum.update(keyval.encode("utf-8"))
    return csum.hexdigest()


# ignored keys when calculating oid
_OID_IGNORED_KEYS = {
    "interval", "diff_mode", "on_error_wait", "report_unchanged",
    "output", 'diff_options',
    "jamendo_client_id", "github_user", "github_token",
}

# configuration defaults for inputs
DEFAULTS = {
    "kind": "url",
    "on_error_wait": "12h",
    "diff_mode": "ndiff",
}


def _conf2string(conf: dict) -> list:
    """Convert `conf` dictionary to list of strings."""
    kvs = []

    def append(parent, item):
        if isinstance(item, dict):
            for key, val in item.items():
                if not key.startswith("_") and key not in _OID_IGNORED_KEYS \
                        and val != DEFAULTS.get(key):
                    append(parent + "." + key, val)
        elif isinstance(item, (list, tuple)):
            for idx, itm in enumerate(item):
                append(parent + "." + str(idx), itm)
        else:
            kvs.append(parent + ":" + str(item))

    append("", conf)
    kvs.sort()
    return kvs


# keys to use as name
_NAME_KEY_TO_TRY = ["name", "url", "cmd"]


def get_input_name(conf: dict, idx=None) -> str:
    """Return input name according to configuration."""
    for key in _NAME_KEY_TO_TRY:
        name = conf.get(key)
        if name:
            return name
    return "Source " + str(idx)


def _check_dir_for_file(fpath: str):
    """Check is directory for file exists; create if missing."""
    dpath = os.path.dirname(fpath)
    if not os.path.isdir(dpath):
        os.makedirs(dpath)


# locking
def _try_lock():
    """Check and create lock file - prevent running application twice.

    Return lock file handler.
    """
    lock_file_path = _find_config_file("app.lock", False)
    _check_dir_for_file(lock_file_path)
    try:
        if fcntl is not None:
            lock_file = open(lock_file_path, "w")
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            if os.path.isfile(lock_file_path):
                _LOG.error("another instance detected (lock file exists) "
                           "- exiting")
                return None
            lock_file = open(lock_file_path, "w")
        return lock_file
    except IOError as err:
        import errno
        if err.errno == errno.EAGAIN:
            _LOG.error("another instance detected - exiting")
        else:
            _LOG.exception("locking failed: %s", err)
    return None


def _unlock(fhandler):
    """Unlock app - remove lock file ``fhandler``."""
    fname = fhandler.name
    try:
        fhandler.close()
        os.unlink(fname)
    except IOError as err:
        _LOG.error("unlock error: %s", err)


@contextmanager
def lock():
    """Lock application by lock file."""
    fhandler = _try_lock()
    try:
        if fhandler:
            yield
    finally:
        if fhandler:
            _unlock(fhandler)
