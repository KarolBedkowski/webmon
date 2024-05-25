# Copyright © 2022 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""
Proxy request via webmon application.
"""

import typing as ty

import requests
import structlog
from flask import Blueprint, Response

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)
BP = Blueprint("proxy", __name__, url_prefix="/proxy")

_EXCLUDED_HEADERS = [
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
]


@BP.route("/<path:path>", methods=["GET"])  # type:ignore
def proxy(path: str) -> ty.Any:  # noqa: ANN401
    _LOG.debug("web proxy: proxy request", path=path)

    resp = requests.get(path, timeout=30)
    headers = [
        (name, value)
        for (name, value) in resp.raw.headers.items()
        if name.lower() not in _EXCLUDED_HEADERS
    ]

    _LOG.debug("web proxy: request finished", status_code=resp.status_code)
    return Response(resp.content, resp.status_code, headers)
