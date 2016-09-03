#!/usr/bin/python3
"""
Main functions.

Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import os.path
import datetime
import logging
import argparse
import imp
import time
import pprint
import locale

from . import cache
from . import config
from . import inputs
from . import logging_setup
from . import filters
from . import outputs
from . import common
from . import comparators


__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

VERSION = "0.1"
DEFAULT_DIFF_MODE = "ndiff"

_LOG = logging.getLogger("main")


def compare_contents(prev_content: str, content: str, ctx: common.Context,
                     result: common.Result) -> (str, dict):
    comparator = comparators.get_comparator(
        ctx.input_conf["diff_mode"] or DEFAULT_DIFF_MODE, ctx)

    ctx.log_debug("ctx: %r", ctx.metadata)
    update_date = result.meta.get('update_date') or time.time()

    diff = "\n".join(comparator.compare(
        prev_content.split("\n"),
        str(datetime.datetime.fromtimestamp(update_date)),
        content.split("\n"),
        str(datetime.datetime.now())))
    return diff, {'comparator_opts': comparator.opts}


def _check_last_error_time(ctx: common.Context) -> bool:
    """
    Return true when load error occurred and still `on_error_wait` interval
    not pass.
    """
    last_error = ctx.metadata.get('last_error')
    on_error_wait = ctx.input_conf.get('on_error_wait')
    if last_error and on_error_wait:
        on_error_wait = common.parse_interval(on_error_wait)
        return time.time() < last_error + on_error_wait
    return False


def _load_content(loader, ctx: common.Context) -> common.Result:
    start = time.time()
    # load list of parts
    result = loader.load()
    if not result.meta.get('update_date'):
        result.meta['update_date'] = time.time()

    if ctx.debug:
        ctx.log_debug("loaded: %s", result)
        result.debug['loaded_in'] = time.time() - start
        result.debug['items'] = len(result.items)

    # apply filters
    for fltcfg in ctx.input_conf.get('filters') or []:
        flt = filters.get_filter(fltcfg, ctx)
        if not flt:
            continue
        result = flt.filter(result)
        if ctx.debug:
            ctx.log_debug("filtered by %s: %s", flt, pprint.saferepr(result))

    if not result.items:
        result.append(common.Item("<no data>"))

    result.meta['update_duration'] = time.time() - start
    result.meta['update_date'] = time.time()
    if ctx.debug:
        ctx.log_debug("result: %s", result)
    return result


def process_content(ctx: common.Context, result: common.Result) -> (str, str):
    """Detect content status (changes). Returns content formatted to
    write into cache.
    """
    content = format_content(result)
    status = result.meta['status']

    if status == common.STATUS_UNCHANGED:
        ctx.log_debug("loading - unchanged content")
        if ctx.input_conf.get("report_unchanged", False):
            # unchanged content, but report
            ctx.output.put(result, content)
        return content, common.STATUS_UNCHANGED

    prev_content = ctx.cache.get(ctx.oid)
    if prev_content is None:
        # new content
        ctx.log_debug("loading - new content")
        result.meta['status'] = common.STATUS_NEW
        ctx.output.put(result, content)
        return content, common.STATUS_NEW

    if prev_content != content:
        # changed content
        ctx.log_debug("loading - changed content, making diff")
        diff, new_meta = compare_contents(prev_content, content, ctx, result)
        if new_meta:
            result.meta.update(new_meta)
        result.meta['status'] = common.STATUS_CHANGED
        ctx.output.put(result, diff)
        return content, common.STATUS_CHANGED

    ctx.log_debug("loading - unchanged content")
    if ctx.input_conf.get("report_unchanged", False):
        # unchanged content, but report
        result.meta['status'] = common.STATUS_UNCHANGED
        ctx.output.put(result, content)
    return content, common.STATUS_UNCHANGED


def write_metadata_on_error(ctx, metadata, error_msg):
    metadata = metadata or {}
    metadata['update_date'] = time.time()
    metadata['last_error'] = time.time()
    metadata['last_error_msg'] = str(error_msg)
    metadata['status'] = common.STATUS_ERROR
    ctx.cache.put_meta(ctx.oid, metadata)


def _load(ctx: common.Context) -> bool:
    ctx.log_debug("start loading")
    ctx.metadata = ctx.cache.get_meta(ctx.oid) or {}

    # find loader
    loader = inputs.get_input(ctx)

    # check, is update required
    # TODO: check last error
    if not ctx.args.force and not loader.need_update():
        ctx.log_info("no update required")
        return False

    # load
    ctx.log_info("loading...")
    try:
        result = _load_content(loader, ctx)
    except common.InputError as err:
        write_metadata_on_error(ctx, None, err)
        return common.STATUS_ERROR

    if not result.title:
        result.title = ctx.name

    if result.meta['status'] == common.STATUS_ERROR:
        write_metadata_on_error(ctx, result.meta, err)
        return common.STATUS_ERROR

    content, status = process_content(ctx, result)
    result.meta['status'] = status
    ctx.cache.put(ctx.oid, content)
    ctx.cache.put_meta(ctx.oid, result.meta)
    ctx.log_info("loading done")
    return True


def format_content(result: common.Result) -> str:
    res = []
    for itm in result.items:
        if itm.title:
            res.append(itm.title)
            res.append("-" * len(itm.title))
        info = []
        if itm.date:
            info.append(itm.date)
        if itm.author:
            info.append(itm.author)
        if itm.link:
            info.append(itm.link)
        if info:
            res.append(" | ".join(info))

        res.append(itm.content)
        res.append("")
    return "\n".join(res)


def _parse_options():
    parser = argparse.ArgumentParser(description='WebMon ' + VERSION)
    parser.add_argument('-i', '--inputs',
                        help='yaml file containing inputs definition'
                        ' (default inputs.yaml)')
    parser.add_argument('-c', '--config',
                        help='configuration filename (default config.yaml)')
    parser.add_argument("-s", "--silent", action="store_true",
                        help="show only errors and warnings")
    parser.add_argument("-d", "--debug", action="store_true",
                        help="print debug informations")
    parser.add_argument('--log',
                        help='log file name')
    parser.add_argument('--cache-dir',
                        default="~/.cache/webmon/cache",
                        help='path to cache directory')
    parser.add_argument('--partials-dir',
                        default="~/.cache/webmon/partials",
                        help='path to dir with partial reports')
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
    parser.add_argument("--stats-file", help="write stats to file")
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


def _show_abilities():
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


def _list_inputs(inps, debug):
    print("Inputs:")
    for idx, inp_conf in enumerate(inps, 1):
        name = config.get_input_name(inp_conf, idx)
        act = "" if inp_conf.get("enable", True) else "DISABLE"
        oid = config.gen_input_oid(inp_conf) if debug else ""
        print(" {:2d} {:<40s}".format(idx, name), act, oid)


def _update_one(ctx):
    try:
        return _load(ctx)
    except IOError as err:
        ctx.log_error("loading error: %s", str(err).replace("\n", "; "))
        ctx.output.put_error(ctx, str(err))
    return True


def _build_defaults(args, conf):
    defaults = {}
    defaults.update(config.DEFAULTS)
    defaults.update(conf.get("defaults") or {})
    defaults["diff_mode"] = args.diff_mode
    return defaults


def _update(args, inps, conf, selection=None):
    try:
        gcache = cache.Cache(os.path.expanduser(args.cache_dir))
    except IOError:
        _LOG.error("Init cache error")
        return

    try:
        output = outputs.Output(args.partials_dir)
    except RuntimeError as err:
        _LOG.error("Init parts dir error: %s", err)
        return

    # defaults for inputs
    defaults = _build_defaults(args, conf)

    for idx, iconf in enumerate(inps, 1):
        if not selection or idx in selection:
            params = common.apply_defaults(defaults, iconf)
            ctx = common.Context(params, gcache, idx, output, args)
            _update_one(ctx)


def main():
    """Main function."""

    locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())

    args = _parse_options()
    logging_setup.setup(args.log, args.debug, args.silent)

    _load_user_classes()

    if args.abilities:
        _show_abilities()
        return

    inps = config.load_inputs(args.inputs)
    if not inps:
        return

    if args.list_inputs:
        with config.lock():
            _list_inputs(inps, args.debug)
        return

    conf = config.load_configuration(args.config)
    if not conf:
        return

    selection = None
    if args.sel:
        try:
            selection = set(int(idx.strip()) for idx in args.sel.split(","))
        except ValueError:
            _LOG.error("Invalid --sel parameter - expected numbers separated"
                       "by comma")
            return

    try:
        with config.lock():
            _update(args, inps, conf, selection)
    except RuntimeError:
        pass


if __name__ == "__main__":
    main()
