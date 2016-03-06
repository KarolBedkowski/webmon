#!/usr/bin/python3

import logging
import yaml

_LOG = logging.getLogger(__name__)


def load_configuration(filename):
    _LOG.debug("load_configuration from %s", filename)
    with open(filename) as fin:
        return yaml.load(fin)


def load_inputs(filename):
    _LOG.debug("load_inputs from %s", filename)
    with open(filename) as fin:
        return [doc for doc in yaml.load_all(fin) if doc]
