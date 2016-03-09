#!/usr/bin/python3
"""
Configuration related functions.
"""

import logging
import os.path
import yaml

_LOG = logging.getLogger(__name__)


def load_configuration(filename):
    _LOG.debug("load_configuration from %s", filename)
    if not os.path.isfile(filename):
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
