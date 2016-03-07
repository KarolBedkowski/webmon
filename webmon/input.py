#!/usr/bin/python3

import subprocess
import hashlib
import email.utils
import logging

import requests


_LOG = logging.getLogger(__name__)


class NotModifiedError(RuntimeError):
    """Exception raised on HTTP 304 responses"""


class NotFoundError(RuntimeError):
    """Exception raised on HTTP 400 responses"""


class ParamError(RuntimeError):
    """Exception raised on missing param"""


class CmdError(RuntimeError):
    """Exception raised on command error"""


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
                raise ParamError("missing parameter " + param)

    def load(self, last):
        raise NotImplementedError()

    def get_oid(self):
        csum = hashlib.sha1()
        csum.update(self.name.encode("utf-8"))
        for key in self._oid_keys or []:
            csum.update(self.conf.get(key, "").encode("utf-8"))
        return csum.hexdigest()


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
            raise NotModifiedError()
        if response.status_code != 200:
            raise NotModifiedError()
        return response.text


class CmdInput(AbstractInput):
    """docstring for WebInput"""

    name = "cmd"
    _oid_keys = ("cmd", )
    _required_params = ("cmd", )

    def load(self, last):
        conf = self.conf
        process = subprocess.Popen(conf['cmd'],
                                   stdout=subprocess.PIPE, shell=True)
        stdout, _ = process.communicate()
        result = process.wait()
        if result == 0:
            return stdout.decode('utf-8')

        raise CmdError(result)


def get_input(conf):
    kind = conf.get("kind") or "url"

    for rcls in getattr(AbstractInput, "__subclasses__")():
        if getattr(rcls, 'name') == kind:
            inp = rcls(conf)
            inp.validate()
            return inp

    return None
