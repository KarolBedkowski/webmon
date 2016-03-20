#!/usr/bin/python3
"""
Configuration related functions.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import logging
import os.path
import copy
import hashlib

import yaml

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

_LOG = logging.getLogger(__name__)


def load_configuration(filename):
    """ Load app configuration from `filename`."""
    if not filename:
        filename = _find_config_file("config.yaml")

    _LOG.debug("load_configuration from %s", filename)
    if not filename or not os.path.isfile(filename):
        _LOG.error("Loading configuration file %s error: not found", filename)
        return None
    try:
        with open(filename) as fin:
            return yaml.load(fin)
    except Exception as err:
        _LOG.error("Loading configuration from file %s error: %s", filename,
                   err)
    return None


def load_inputs(filename):
    """ Load inputs configuration from `filename`"""
    if not filename:
        filename = _find_config_file("inputs.yaml")

    _LOG.debug("load_inputs from %s", filename)
    if not os.path.isfile(filename):
        _LOG.error("Loading inputs file %s error: not found", filename)
        return None
    try:
        with open(filename) as fin:
            inps = [doc for doc in yaml.load_all(fin)
                    if doc and doc.get("enable", True)]
            if not inps:
                _LOG.error("no valid/enabled inputs found")
            return inps
    except Exception as err:
        _LOG.error("Loading inputs from file %s error: %s", filename, err)
    return None


def apply_defaults(defaults, conf):
    """ Deep copy & update `defaults` dict with `conf`."""
    result = copy.deepcopy(defaults)

    def update(dst, src):
        for key, val in src.items():
            if isinstance(val, dict):
                if key not in dst:
                    dst[key] = {}
                update(dst[key], val)
            else:
                dst[key] = copy.deepcopy(val)

    if conf:
        update(result, conf)

    return result


def _find_config_file(name):
    if os.path.isfile(name):
        return name
    # try ~/.config/webmon/
    bname = os.path.basename(name)
    fpath = os.path.expanduser(os.path.join("~", ".config", "webmon", bname))
    return fpath if os.path.isfile(fpath) else None


def gen_input_oid(conf):
    """ Generate object id according to configuration. """
    oid = conf.get('oid') or conf.get('id')
    if oid:
        return oid
    csum = hashlib.sha1()
    for keyval in _conf2string(conf):
        csum.update(keyval.encode("utf-8"))
    return csum.hexdigest()


# ignored keys when calculating oid
_OID_IGNORED_KEYS = {"interval", "diff_mode"}

def _conf2string(conf):
    """ Convert dictionary to list of strings. """
    kvs = []

    def append(parent, item):
        if isinstance(item, dict):
            for key, val in item.items():
                if not key.startswith("_") and key not in _OID_IGNORED_KEYS:
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


def get_input_name(conf, idx):
    """ Return input name according to configuration. """
    for key in _NAME_KEY_TO_TRY:
        name = conf.get(key)
        if name:
            return name
    return "Source %d" % idx
