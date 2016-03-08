#!/usr/bin/python3

import subprocess
import hashlib
import email.utils
import logging
import time

import requests

from . import common

_LOG = logging.getLogger(__name__)


class AbstractInput(object):
    """docstring for AbstractInput"""

    name = None
    _oid_keys = None
    _required_params = None

    def __init__(self, conf):
        super(AbstractInput, self).__init__()
        self.conf = conf

    def validate(self):
        for param in self._required_params or []:
            if not self.conf.get(param):
                raise common.ParamError("missing parameter " + param)

    def load(self, last):
        raise NotImplementedError()

    def get_oid(self):
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

        append("", self.conf)
        kvs.sort()

        csum = hashlib.sha1()
        csum.update(self.name.encode("utf-8"))
        for keyval in kvs:
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
        return name


class WebInput(AbstractInput):
    """docstring for WebInput"""

    name = "url"
    _oid_keys = ("url", )
    _required_params = ("url", )

    def load(self, last):
        conf = self.conf
        headers = {
            'User-agent': "Mozilla"
        }
        if last:
            headers['If-Modified-Since'] = email.utils.formatdate(last)
        _LOG.debug("load_from_web headers: %r", headers)
        response = requests.request(url=conf['url'], method='GET',
                                    headers=headers)
        response.raise_for_status()
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
    """docstring for WebInput"""

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
        result = process.wait()
        if result == 0:
            yield stdout.decode('utf-8')
            return

        err = ("Err: " + str(result),
               (stdout or b"").decode("utf-8"),
               (stderr or b"").decode('utf-8'))
        errstr = "\n".join(line.strip() for line in err if line)
        raise common.InputError(errstr.strip())


def get_input(conf):
    kind = conf.get("kind") or "url"

    for rcls in getattr(AbstractInput, "__subclasses__")():
        if getattr(rcls, 'name') == kind:
            inp = rcls(conf)
            inp.validate()
            return inp

    _LOG.warn("unknown input kind: %s", kind)
    return None


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
