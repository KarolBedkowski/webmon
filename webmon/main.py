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

# TODO: wprowadzic podzial zgodny z ascii
PARTS_SEP = "\n\n-----\n\n"

_LOG = logging.getLogger("main")


def _compare(prev_content: str, content: str, ctx: common.Context) -> str:
    comparator = comparators.get_comparator(
        ctx.conf["diff_mode"] or DEFAULT_DIFF_MODE, ctx)

    ctx.opt.update(comparator.opts)

    diff = "\n".join(comparator.compare(
        prev_content.split("\n"),
        str(datetime.datetime.fromtimestamp(ctx.last_updated)),
        content.split("\n"),
        str(datetime.datetime.now())))
    return diff


def _check_last_error_time(ctx: common.Context) -> bool:
    """
    Return true when load error occurred and still `on_error_wait` interval
    not pass.
    """
    last_error = ctx.metadata.get('last_error')
    on_error_wait = ctx.conf.get('on_error_wait')
    if last_error and on_error_wait:
        on_error_wait = common.parse_interval(on_error_wait)
        return time.time() < last_error + on_error_wait
    return False


def _is_recovery_accepted(ctx: common.Context, mtime: int,
                          last_updated: int) -> bool:
    """Check is recovered file is valid by modified time.

    :param ctx: common.Context type: common.Context
    :param mtime: timestamp of recovered file
    :param last_updated: last updated valid file
    """
    interval = common.parse_interval(ctx.conf['interval'])
    if last_updated:
        return last_updated + interval < mtime
    # no previous valid file found
    return time.time() - mtime < interval


def _load_content(loader, ctx: common.Context) -> (str, common.Context):
    start = time.time()
    # load list of parts
    parts = loader.load()
    if ctx.debug:
        parts = list(parts)
        ctx.log_debug("loaded: %s", pprint.saferepr(parts))

    # apply filters
    for fltcfg in ctx.conf.get('filters') or []:
        flt = filters.get_filter(fltcfg, ctx)
        if not flt:
            continue
        parts = flt.filter(parts)
        if ctx.debug:
            parts = list(parts)
            ctx.log_debug("filtered by %s: %s", flt, pprint.saferepr(parts))

    content = PARTS_SEP.join(ppart for ppart in
                             (part.rstrip() for part in parts)
                             if ppart)
    content = content or "<no data>"
    ctx.debug_data['load_time'] = time.time() - start
    if ctx.debug:
        ctx.log_debug("result: %s", pprint.saferepr(content))
    return content, ctx


def _clean_meta_on_success(metadata: dict):
    if 'last_error' in metadata:
        del metadata['last_error']
    if 'last_error_msg' in metadata:
        del metadata['last_error_msg']
    return metadata


def _add_to_output(ctx: common.Context, prev_content: str, content: str) \
        -> common.Context:
    if prev_content is None:
        # new content
        ctx.log_debug("loading - new content")
        ctx.output.add_new(ctx, content)
    elif prev_content != content:
        # changed content
        ctx.log_debug("loading - changed content, making diff")
        diff = _compare(prev_content, content, ctx)
        ctx.output.add_changed(ctx, diff)
    else:
        ctx.log_debug("loading - unchanged content")
        if ctx.conf.get("report_unchanged", False):
            # unchanged content, but report
            ctx.output.add_unchanged(ctx, prev_content)
    return ctx


def _try_recover(ctx: common.Context) -> (bool, str, common.Context):
    """Try recover content & metadata; if not success - load last metadata."""
    oid = ctx.oid
    last_updated = ctx.cache.get_mtime(oid)
    content, mtime, meta = ctx.cache.get_recovered(oid)
    if content is not None \
            and _is_recovery_accepted(ctx, mtime, last_updated):
        ctx.last_updated = mtime
        ctx.metadata.update(meta or {})
        ctx.log_info("recovered content")
        return True, content, ctx

    ctx.last_updated = last_updated
    ctx.metadata.update(ctx.cache.get_meta(oid) or {})
    return False, None, ctx


def _load(ctx: common.Context) -> bool:
    ctx.log_debug("start loading")

    # try to recover, load meta
    recovered, content, ctx = _try_recover(ctx)

    if not ctx.args.force and _check_last_error_time(ctx):
        ctx.log_info("skipping - still waiting after error")
        return False

    loader = inputs.get_input(ctx)
    if not ctx.args.force and not loader.need_update() and not recovered:
        ctx.log_info("no update required")
        return False

    prev_content = ctx.cache.get(ctx.oid)
    if not recovered:
        ctx.log_info("loading...")
        try:
            content, ctx = _load_content(loader, ctx)
        except common.NotModifiedError:
            content = prev_content
        except common.InputError as err:
            ctx.metadata['last_error'] = time.time()
            ctx.metadata['last_error_msg'] = str(err)
            ctx.cache.put_meta(ctx.oid, ctx.metadata)
            raise

    ctx.metadata = _clean_meta_on_success(ctx.metadata)
    if ctx.debug:
        ctx.log_debug("diff prev: %s", pprint.saferepr(prev_content))
        ctx.log_debug("diff content: %s", pprint.saferepr(content))

    ctx = _add_to_output(ctx, prev_content, content)
    ctx.cache.put(ctx.oid, content)
    ctx.cache.put_meta(ctx.oid, ctx.metadata)
    ctx.log_info("loading done")
    return True


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
    except Exception as err:
        ctx.log_error("loading error: %s", str(err).replace("\n", "; "))
        ctx.output.add_error(ctx, str(err))
    return True


def _build_defaults(args, conf):
    defaults = {}
    defaults.update(config.DEFAULTS)
    defaults.update(conf.get("defaults") or {})
    defaults["diff_mode"] = args.diff_mode
    return defaults


def _update(args, inps, conf, selection=None):
    start_time = time.time()

    try:
        gcache = cache.Cache(os.path.expanduser(args.cache_dir))
    except IOError:
        _LOG.error("Init cache error")
        return

    output = outputs.OutputManager(conf.get("output"), args)
    if not output.valid:
        _LOG.error("no valid outputs found")
        return

    # defaults for inputs
    defaults = _build_defaults(args, conf)

    def build_context(idx, iconf):
        params = common.apply_defaults(defaults, iconf)
        return common.Context(params, gcache, idx, output, args)

    processed = sum(
        1 if _update_one(build_context(idx, iconf)) else 0
        for idx, iconf in enumerate(inps, 1)
        if not selection or idx in selection)

    duration = time.time() - start_time
    output.write("Generate time: %.2f" % duration)
    status = output.status()
    _LOG.info("Result: %s, inputs: %d, processed: %d",
              ", ".join(key + ": " + str(val)
                        for key, val in status.items()),
              len(inps), processed)

    if output.errors_cnt < processed:
        # do not commit changes when all inputs failed
        gcache.commmit_temps(not selection)

    if args.stats_file:
        with open(args.stats_file, 'w') as fout:
            fout.write(
                "ts: {} inputs: {} processed: {} new: {} changed: {}"
                " unchanged: {} errors: {} duration: {}".format(
                    int(start_time), len(inps), processed, status['new'],
                    status['changed'], status['unchanged'], status['error'],
                    duration))


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
