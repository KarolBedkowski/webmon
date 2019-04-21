#!/usr/bin/python3
"""
Main functions.

Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.
Licence: GPLv2+
"""

import argparse
from concurrent import futures
import datetime
import imp
import locale
import logging
import os.path
import pprint
import time
import typing as ty

# import typecheck as tc

from . import db, inputs, logging_setup, filters
from . import worker
from . import web

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2019"

VERSION = "0.2"
APP_NAME = "webmon"
DEFAULT_DIFF_MODE = "ndiff"

_LOG = logging.getLogger("main")


def _parse_options():
    parser = argparse.ArgumentParser(description=APP_NAME + " " + VERSION)
    parser.add_argument('-i', '--inputs',
                        help='yaml file containing inputs definition'
                        ' (default inputs.yaml)')
    parser.add_argument('-c', '--config',
                        help='configuration filename (default config.yaml)')
    parser.add_argument("-s", "--silent", action="store_true",
                        help="show only errors and warnings")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show additional informations")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="print debug informations")
    parser.add_argument('--log',
                        help='log file name')
    parser.add_argument('--cache-dir',
                        default="~/.cache/" + APP_NAME,
                        help='path to cache directory')
    parser.add_argument("--force", action="store_true",
                        help="force update all sources")
    parser.add_argument("--diff-mode", choices=['ndiff', 'unified', 'context'],
                        help="default diff mode")
    parser.add_argument("--abilities", action="store_true",
                        help="show available filters/inputs/outputs/"
                        "comparators")
    parser.add_argument("--list-inputs", action="store_true",
                        help="show configured inputs")
    parser.add_argument("--sel", help="select (by idx, separated by comma) "
                        "inputs to update")
    parser.add_argument("--tasks", help="background task to launch",
                        type=int, default=2)
    return parser.parse_args()


def _show_abilities_cls(title, base_cls):
    print(title)
    for name, cls in common.get_subclasses_with_name(base_cls):
        print("  -", name)
        if hasattr(cls, "description"):
            print("    " + cls.description)

        if hasattr(cls, "params") and cls.params:
            print("    Parameters:")
            for param in cls.params:
                print("     - {:<15s}\t{:<20s}\tdef={!r:<10}\treq={!r}".format(
                    *param))
    print()


def show_abilities():
    _show_abilities_cls("Inputs:", inputs.AbstractInput)
    _show_abilities_cls("Outputs:", outputs.AbstractOutput)
    _show_abilities_cls("Filters:", filters.AbstractFilter)
    _show_abilities_cls("Comparators:", comparators.AbstractComparator)


def _load_user_classes():
    users_scripts_dir = os.path.expanduser("~/.local/share/webmon")
    if not os.path.isdir(users_scripts_dir):
        return

    for fname in os.listdir(users_scripts_dir):
        fpath = os.path.join(users_scripts_dir, fname)
        if os.path.isfile(fpath) and fname.endswith(".py") \
                and not fname.startswith("_"):
            _LOG.debug("loading %r", fpath)
            try:
                imp.load_source(fname[:-3], fpath)
            except ImportError as err:
                _LOG.error("Importing '%s' error %s", fpath, err)


# @tc.typecheck
def _list_inputs(inps, conf, args):
    print("Inputs:")
    defaults = _build_defaults(args, conf)
    for idx, inp_conf in enumerate(inps, 1):
        params = common.apply_defaults(defaults, inp_conf)
        name = config.get_input_name(params, idx)
        act = "" if params.get("enable", True) else "DISABLE"
        print(" {:2d} {:<40s} {}".format(idx, name, act))


# @tc.typecheck
def _list_inputs_dbg(inps, conf, args):
    try:
        gcache = cache.Cache(os.path.join(
            os.path.expanduser(args.cache_dir), "cache"))
    except IOError:
        _LOG.error("Init cache error")
        return
    print("Inputs:")
    defaults = _build_defaults(args, conf)
    for idx, inp_conf in enumerate(inps, 1):
        params = common.apply_defaults(defaults, inp_conf)
        ctx = common.Context(params, gcache, idx, None, args)
        ctx.metadata = ctx.cache.get_meta(ctx.oid) or {}

        if ctx.last_updated:
            last_update = time.strftime("%x %X",
                                        time.localtime(ctx.last_updated))
        else:
            last_update = 'never loaded'

        loader = inputs.get_input(ctx)
        next_update_ts = loader.next_update()
        if next_update_ts:
            next_update = time.strftime(
                "%x %X", time.localtime(next_update_ts))
        else:
            next_update = 'now'

        print(" {:2d} {:<40s}  {}  last: {}  next: {}  {}  {}".format(
            idx,
            config.get_input_name(params, idx),
            "ENB" if params.get("enable", True) else "DIS",
            last_update, next_update,
            ctx.metadata.get('status'),
            config.gen_input_oid(params)
        ))


def _build_defaults(args, conf):
    defaults = {}
    defaults.update(config.DEFAULTS)
    defaults.update(conf.get("defaults") or {})
    defaults["diff_mode"] = args.diff_mode
    return defaults


def load_all(args, inps, conf, selection=None):
    """ Load all (or selected) inputs"""
    metrics.configure(conf)
    start = time.time()
    try:
        gcache = cache.Cache(os.path.join(
            os.path.expanduser(args.cache_dir), "cache"))
    except IOError:
        _LOG.error("Init cache error")
        return

    partial_reports_dir = os.path.join(
        os.path.expanduser(args.cache_dir), "partials")

    try:
        output = outputs.OutputManager(conf, partial_reports_dir)
    except RuntimeError as err:
        _LOG.error("Init parts dir error: %s", err)
        return

    # defaults for inputs
    defaults = _build_defaults(args, conf)

    def task(idx, iconf):
        params = common.apply_defaults(defaults, iconf)
        ctx = common.Context(params, gcache, idx, output, args)
        try:
            load(ctx)
        except Exception as err:  # pylint: disable=broad-except
            ctx.log_exception("loading error: %s", err)
            ctx.output.put_error(ctx, str(err))
        del ctx

    with futures.ThreadPoolExecutor(max_workers=args.tasks or 2) as ex:
        wait_for = [
            ex.submit(task, idx, iconf)
            for idx, iconf in enumerate(inps, 1)
            if not selection or idx in selection
        ]

        futures.wait(wait_for)

    _LOG.info("Loading: all done")

    metrics.COLLECTOR.put_loading_summary(time.time() - start)

    footer = " ".join((APP_NAME, VERSION, time.asctime()))
    output.write(footer=footer, debug=args.debug)

    # if processing all files - clean unused / old cache files
    if not selection:
        gcache.clean_cache()

    metrics.COLLECTOR.put_total(time.time() - start)
    metrics.COLLECTOR.write()


def _check_libraries():
    try:
        from lxml import etree
    except ImportError:
        _LOG.warn("missing lxml library")
    try:
        import cssselect
    except ImportError:
        _LOG.warn("missing cssselect library")
    try:
        import html2text
    except ImportError:
        _LOG.warn("missing html2text library")
    try:
        import docutils.core
    except ImportError:
        _LOG.warn("missing docutils library")
    try:
        import yaml
    except ImportError:
        _LOG.warn("missing yaml library")
    try:
        import requests
    except ImportError:
        _LOG.warn("missing requests library")
    try:
        import feedparser
    except ImportError:
        _LOG.warn("missing feedparser library")
    try:
        import github3
    except ImportError:
        _LOG.warn("missing github3 library")


def main():
    """Main function."""

    try:
        locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())
    except locale.Error:
        pass

    args = _parse_options()
    logging_setup.setup(args.log, args.debug, args.silent)

    _check_libraries()
    _load_user_classes()

    if args.abilities:
        show_abilities()
        return

    dbfile = os.path.join(os.path.expanduser(args.cache_dir))
    dbfile = "./webmon.db"
    database = db.DB.initialize(dbfile)

    cworker = worker.CheckWorker(database.clone())
    cworker.start()

    web.start_app(dbfile)

    database.close()


if __name__ == "__main__":
    main()
