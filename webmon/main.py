#!/usr/bin/python3
"""
Main functions.

Copyright (c) Karol Będkowski, 2016

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

#import typecheck as tc

from . import (cache, common, comparators, config, filters, inputs,
               logging_setup, outputs, metrics)

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016"

VERSION = "0.2"
APP_NAME = "webmon"
DEFAULT_DIFF_MODE = "ndiff"

_LOG = logging.getLogger("main")


#@tc.typecheck
def compare_contents(prev_content: str, content: str, ctx: common.Context,
                     result: common.Result) -> ty.Tuple[str, dict]:
    """ Compare contents according to configuration. """
    opts = ctx.input_conf.get("diff_options")
    comparator = comparators.get_comparator(
        ctx.input_conf["diff_mode"] or DEFAULT_DIFF_MODE,
        opts[0] if opts else {})

    update_date = result.meta.get('update_date') or time.time()

    diff, new_meta = comparator.compare(
        prev_content, str(datetime.datetime.fromtimestamp(update_date)),
        content, str(datetime.datetime.now()), ctx, result.meta)

    # ctx.log_debug("compare: diff: %s", diff)
    return diff, {'comparator_opts': new_meta}


#@tc.typecheck
def compare_content_new(content: str, ctx: common.Context,
                        result: common.Result) -> ty.Tuple[str, dict]:
    opts = ctx.input_conf.get("diff_options")
    comparator = comparators.get_comparator(
        ctx.input_conf["diff_mode"] or DEFAULT_DIFF_MODE,
        opts[0] if opts else {})

    diff, new_meta = comparator.new(
        content, str(datetime.datetime.now()), ctx, result.meta)

    return diff, {'comparator_opts': new_meta}


#@tc.typecheck
def check_last_error_time(ctx: common.Context) -> bool:
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


#@tc.typecheck
def load_content(loader, ctx: common.Context) -> common.Result:
    """ Load & filter content """
    start = time.time()
    # load list of parts
    result = loader.load()

    if ctx.debug:
        ctx.log_debug("loaded: %s", result)
        result.debug['loaded_duration'] = time.time() - start
        fltr_start = time.time()
        result.debug['items_loaded'] = len(result.items)
        result.debug['filters_status'] = {}

    # apply filters
    for fltcfg in ctx.input_conf.get('filters') or []:
        flt = filters.get_filter(fltcfg, ctx)
        if not flt:
            ctx.log_error("missing filter: %s", fltcfg)
            continue
        result = flt.filter(result)
        if ctx.debug:
            ctx.log_debug("filtered by %s: %s", flt, pprint.saferepr(result))
            result.debug['filters_status'][flt.name] = len(result.items)

    if ctx.args.debug:
        result.meta['filter_duration'] = time.time() - fltr_start
        result.debug['items_filterd'] = len(result.items)

    result.meta['update_duration'] = time.time() - start
    result.meta['update_date'] = time.time()
    if not result.title:
        result.title = ctx.name
    if ctx.debug:
        ctx.log_debug("result: %s", result)
    return result


#@tc.typecheck
def process_content(ctx: common.Context, result: common.Result) \
        -> ty.Tuple[str, str, ty.Optional[dict], str]:
    """Detect content status (changes). Returns content formatted to
    write into cache.
    Returns (status, diff_result, new metadata, content after processing)
    """
    status = result.status
    if status == common.STATUS_ERROR:
        err = result.meta['error']
        return common.STATUS_ERROR, err, None, None

    prev_content = ctx.cache.get(ctx.oid)
    content = result.format()

    if status == common.STATUS_UNCHANGED:
        ctx.log_debug("loading - unchanged content")
        new_meta = {'comparator_opts': ctx.metadata.get('comparator_opts')}
        return (common.STATUS_UNCHANGED, prev_content, new_meta, prev_content)

    if prev_content is None:
        ctx.log_debug("loading - new content")
        content, new_meta = compare_content_new(content, ctx, result)
        return common.STATUS_NEW, content, new_meta, content

    if prev_content != content:
        ctx.log_debug("loading - changed content, making diff")
        diff, new_meta = compare_contents(prev_content, content, ctx, result)
        return common.STATUS_CHANGED, diff, new_meta, content

    ctx.log_debug("loading - unchanged content")
    new_meta = {'comparator_opts': ctx.metadata.get('comparator_opts')}
    return (common.STATUS_UNCHANGED, prev_content, new_meta, content)


#@tc.typecheck
def create_error_result(ctx: common.Context, error_msg: str) \
        -> common.Result:
    result = common.Result(ctx.oid, ctx.oid)
    result.set_error(error_msg)
    return result


#@tc.typecheck
def load(ctx: common.Context) -> bool:
    """ Load one input defined & configured by context"""
    ctx.log_debug("start loading")
    ctx.metadata = ctx.cache.get_meta(ctx.oid) or {}

    # find loader
    loader = inputs.get_input(ctx)

    # check, is update required
    if not ctx.args.force and not loader.need_update():
        ctx.log_info("no update required")
        return False

    if check_last_error_time(ctx):
        ctx.log_info("waiting after error")
        return False

    # load
    ctx.log_info("loading...")
    try:
        result = load_content(loader, ctx)
    except common.InputError as err:
        ctx.log_error("input error on %s: %r", err.input, err)
        ctx.log_debug("input error params: %s", err.input.dump_debug())
        result = create_error_result(ctx, str(err))
    except common.FilterError as err:
        ctx.log_error("filter error on %s: %r", err.filter, err)
        ctx.log_debug("filter error params: %s", err.filter.dump_debug())
        result = create_error_result(ctx, str(err))

    if ctx.args.debug:
        result.debug['items_final'] = len(result.items)
        result.debug['last_updated'] = ctx.last_updated

    result.status, pres, new_meta, content = process_content(ctx, result)
    if new_meta:
        result.meta.update(new_meta)
    if result.status != common.STATUS_UNCHANGED or \
            ctx.input_conf.get("report_unchanged"):
        ctx.output.put(result, pres, ctx.input_conf)
    if content is not None:
        ctx.cache.put(ctx.oid, content)
    ctx.cache.put_meta(ctx.oid, result.meta)
    metrics.COLLECTOR.put_input(ctx, result)
    ctx.log_info("loading done")
    del loader
    return True


def _parse_options():
    parser = argparse.ArgumentParser(description=APP_NAME + " " + VERSION)
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


#@tc.typecheck
def _list_inputs(inps, conf, args):
    print("Inputs:")
    defaults = _build_defaults(args, conf)
    for idx, inp_conf in enumerate(inps, 1):
        params = common.apply_defaults(defaults, inp_conf)
        name = config.get_input_name(params, idx)
        act = "" if params.get("enable", True) else "DISABLE"
        oid = config.gen_input_oid(params) if args.debug else ""
        print(" {:2d} {:<40s}".format(idx, name), act, oid)


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
        except Exception as err:
            ctx.log_error("loading error: %s",
                          str(err).replace("\n", "; "))
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


def main():
    """Main function."""

    locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())

    args = _parse_options()
    logging_setup.setup(args.log, args.debug, args.silent)

#    if not args.debug:
#        tc.disable()

    _load_user_classes()

    if args.abilities:
        show_abilities()
        return

    inps = config.load_inputs(args.inputs)
    if not inps:
        return

    conf = config.load_configuration(args.config)
    if not conf:
        return

    if args.list_inputs:
        with config.lock():
            _list_inputs(inps, conf, args)
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
            load_all(args, inps, conf, selection)
    except RuntimeError:
        pass


if __name__ == "__main__":
    main()
