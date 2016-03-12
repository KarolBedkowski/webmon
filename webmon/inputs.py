#!/usr/bin/python3
"""
Standard inputs classes.
"""

import subprocess
import hashlib
import email.utils
import logging
import time

import requests

from . import common

_LOG = logging.getLogger(__name__)


class AbstractInput(object):
    """ Abstract/Base class for all inputs """

    # name used in configuration
    name = None
    # key names used to generator name when it missing
    _oid_keys = None
    # required param names
    _required_params = None

    def __init__(self, conf):
        super(AbstractInput, self).__init__()
        self.conf = conf

    def validate(self):
        """ Validate input configuration """
        for param in self._required_params or []:
            if not self.conf.get(param):
                raise common.ParamError("missing parameter " + param)

    def load(self, last):
        """ Load data; return list/generator of items """
        raise NotImplementedError()

    def get_oid(self):
        """ Generate object id according to configuration. """
        csum = hashlib.sha1()
        csum.update(self.name.encode("utf-8"))
        for keyval in _conf2string(self.conf):
            csum.update(keyval.encode("utf-8"))
        return csum.hexdigest()

    def need_update(self, last):
        # default - check interval
        interval = self.conf.get("interval")
        if not interval:
            return True
        interval = _parse_interval(interval)
        return last + interval < time.time()

    @property
    def input_name(self):
        name = self.conf.get('name')
        if name:
            return name
        name = '; '.join([self.conf.get(key) or key for key in self._oid_keys])
        return self.conf['_idx'] + ": " + name


class WebInput(AbstractInput):
    """Load data from web (http/https)"""

    name = "url"
    _oid_keys = ("url", )
    _required_params = ("url", )

    def load(self, last):
        conf = self.conf
        headers = {'User-agent': "Mozilla/5.0 (X11; Linux i686; rv:45.0) "
                                 "Gecko/20100101 Firefox/45.0"}
        if last:
            headers['If-Modified-Since'] = email.utils.formatdate(last)
        _LOG.debug("load_from_web headers: %r", headers)
        try:
            response = requests.request(url=conf['url'], method='GET',
                                        headers=headers,
                                        timeout=60)
            response.raise_for_status()
        except requests.exceptions.ReadTimeout:
            raise common.InputError("timeout")
        except Exception as err:
            raise common.InputError(err)
        if response.status_code == 304:
            response.close()
            raise common.NotModifiedError()
        if response.status_code != 200:
            err = "Response code: %d" % response.status_code
            if response.text:
                err += "\n" + response.text
            response.close()
            raise common.InputError(err)
        yield response.text
        response.close()


class CmdInput(AbstractInput):
    """Load data from command"""

    name = "cmd"
    _oid_keys = ("cmd", )
    _required_params = ("cmd", )

    def load(self, last):
        conf = self.conf
        _LOG.debug("CmdInput execute: %r", conf['cmd'])
        process = subprocess.Popen(conf['cmd'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   shell=True)
        stdout, stderr = process.communicate()
        result = process.wait(60)
        if result != 0:
            err = ("Err: " + str(result), (stdout or b"").decode("utf-8"),
                   (stderr or b"").decode('utf-8'))
            errstr = "\n".join(line.strip() for line in err if line)
            raise common.InputError(errstr.strip())

        yield stdout.decode('utf-8')


def get_input(conf):
    """ Get input class according to configuration """
    kind = conf.get("kind") or "url"
    scls = common.find_subclass(AbstractInput, kind)
    if scls:
        inp = scls(conf)
        inp.validate()
        return inp

    _LOG.warning("unknown input kind: %s; skipping input", kind)


def _parse_interval(instr):
    if isinstance(instr, (int, float)):
        return instr
    mplt = 1
    if instr.endswith("m"):
        mplt = 60
        instr = instr[:-1]
    elif instr.endswith("h"):
        mplt = 3600
        instr = instr[:-1]
    elif instr.endswith("d"):
        mplt = 86400
        instr = instr[:-1]
    elif instr.endswith("w"):
        mplt = 604800
        instr = instr[:-1]
    else:
        raise ValueError("invalid interval '%s'" % instr)
    try:
        return int(instr) * mplt
    except ValueError:
        raise ValueError("invalid interval '%s'" % instr)


def _conf2string(conf):
    """ Convert dictionary to list of strings. """
    kvs = []

    def append(parent, item):
        if isinstance(item, dict):
            for key, val in item.items():
                if not key.startswith("_"):
                    append(parent + "." + key, val)
        elif isinstance(item, (list, tuple)):
            for idx, itm in enumerate(item):
                append(parent + "." + str(idx), itm)
        else:
            kvs.append(parent + ":" + str(item))

    append("", conf)
    kvs.sort()
    return kvs
