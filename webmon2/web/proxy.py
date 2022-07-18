#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2022 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Proxy request via webmon application.
"""

import logging
import typing as ty

import requests
from flask import Blueprint, Response

_LOG = logging.getLogger(__name__)
BP = Blueprint("proxy", __name__, url_prefix="/proxy")

_EXCLUDED_HEADERS = [
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
]


@BP.route("/<path:path>", methods=["GET"])
def proxy(path: str) -> ty.Any:
    _LOG.debug("proxy request to: %s", path)

    resp = requests.get(path)
    headers = [
        (name, value)
        for (name, value) in resp.raw.headers.items()
        if name.lower() not in _EXCLUDED_HEADERS
    ]

    _LOG.debug("proxy request result: status: %r", resp.status_code)
    return Response(resp.content, resp.status_code, headers)
