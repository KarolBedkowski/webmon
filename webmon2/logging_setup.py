# ruff:  noqa: PLW0603
"""Logging setup.
Copyright (c) Karol Będkowski, 2014-2022

This file is part of webmon.
Licence: GPLv2+
"""

import logging
import sys
from http.client import HTTPConnection

import structlog

DEBUG = False
SILENT = False


class NoMetricsLogFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter that remove successful request to /metrics endpoint"""
        return (
            record.levelno != logging.INFO
            or record.name != "werkzeug"
            or '/metrics HTTP/1.1" 200' not in record.getMessage()
        )


def setup(log_fmt: str, debug: bool = False, silent: bool = False) -> None:
    """Setup logging.

    Args:
    :param filename: (str, optional) log file name
    :param debug: (bool) run in debug mode (all messages)
    :param silent: (bool) show only warnings/errors
    """
    global SILENT, DEBUG  # pylint: disable=global-statement;
    SILENT = silent
    DEBUG = debug

    logger = logging.getLogger()
    log_req = logging.getLogger("requests")
    log_github3 = logging.getLogger("github3")
    log_werkzeug = logging.getLogger("werkzeug")
    structlog_level = logging.INFO

    if debug:
        logger.setLevel(logging.DEBUG)
        log_req.setLevel(logging.DEBUG)
        log_github3.setLevel(logging.DEBUG)
        log_werkzeug.setLevel(logging.DEBUG)
        structlog_level = logging.DEBUG

        # enable debug in utllib3
        requests_log = logging.getLogger("urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True
        HTTPConnection.debuglevel = 1
    elif silent:
        logger.setLevel(logging.WARNING)
        log_req.setLevel(logging.WARNING)
        log_github3.setLevel(logging.WARNING)
        logger.addFilter(NoMetricsLogFilter())
        log_werkzeug.addFilter(NoMetricsLogFilter())
        structlog_level = logging.WARNING
    else:
        logger.setLevel(logging.INFO)
        log_req.setLevel(logging.WARNING)
        log_github3.setLevel(logging.WARNING)
        logger.addFilter(NoMetricsLogFilter())
        log_werkzeug.addFilter(NoMetricsLogFilter())

    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.contextvars.merge_contextvars,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                # structlog.processors.CallsiteParameter.FILENAME,
                # structlog.processors.CallsiteParameter.FUNC_NAME,
                # structlog.processors.CallsiteParameter.LINENO,
                # structlog.processors.CallsiteParameter.PATHNAME,
                # structlog.processors.CallsiteParameter.THREAD,
                structlog.processors.CallsiteParameter.THREAD_NAME,
            }
        ),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
    ]

    if sys.stderr.isatty():
        # console
        if log_fmt == "logfmt":
            processors = [
                structlog.processors.format_exc_info,
                structlog.processors.dict_tracebacks,
                structlog.processors.LogfmtRenderer(),
            ]
        else:
            processors = [structlog.dev.ConsoleRenderer(colors=True)]

    elif log_fmt == "console":
        processors = [structlog.dev.ConsoleRenderer(colors=False)]
    else:
        processors = [
            structlog.processors.dict_tracebacks,
            structlog.processors.LogfmtRenderer(),
        ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.make_filtering_bound_logger(structlog_level),
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # These run ONLY on `logging` entries that do NOT originate within
        # structlog.
        foreign_pre_chain=shared_processors,
        # These run on ALL entries after the pre_chain is done.
        processors=[
            # Remove _record & _from_structlog.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *processors,
        ],
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    log = logging.getLogger("logging")
    log.debug("logging_setup() finished")
    structlog.get_logger("structlog").debug(
        "setup finished", log_fmt=log_fmt, debug=debug, silent=silent
    )
