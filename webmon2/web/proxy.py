#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2022 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""

"""

import logging
import typing as ty

import requests
from flask import Blueprint, Response, abort, request

_LOG = logging.getLogger(__name__)
BP = Blueprint("proxy", __name__, url_prefix="/proxy")


@BP.route("/<path:path>", methods=["GET"])
def proxy(path: str) -> ty.Any:
    if request.method != "GET":
        abort(401)

    resp = requests.get(path)
    excluded_headers = [
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
    ]
    headers = [
        (name, value)
        for (name, value) in resp.raw.headers.items()
        if name.lower() not in excluded_headers
    ]
    response = Response(resp.content, resp.status_code, headers)

    return response
