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


def _check_params(conf, required):
    for req in required:
        if not conf.get(req):
            raise ParamError("missing param: %s" % req)


def load_from_web(conf, last):
    _check_params(conf, ("url", ))
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


def load_from_cmd(conf, _last):
    _check_params(conf, ("cmd", ))
    process = subprocess.Popen(conf['cmd'], stdout=subprocess.PIPE,
                               shell=True)
    stdout, _ = process.communicate()
    result = process.wait()
    if result == 0:
        return stdout.decode('utf-8')

    raise CmdError(result)


def get_input(conf):
    kind = conf.get("kind")
    if kind == "cmd":
        return load_from_cmd
    # default
    return load_from_web


_KEYS_FOR_KIND = {
    "cmd": ["cmd"],
    "url": ["url"],
}


def get_oid(conf):
    kind = conf.get("kind", "url")
    keys = _KEYS_FOR_KIND[kind]
    csum = hashlib.sha1()
    csum.update(kind.encode("utf-8"))
    for key in keys:
        csum.update(conf.get(key, "").encode("utf-8"))
    return csum.hexdigest()
