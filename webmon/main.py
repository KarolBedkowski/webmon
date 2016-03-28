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


def _gen_diff(prev_content, content, diff_mode, context):
    comparator = comparators.get_comparator(
        diff_mode or DEFAULT_DIFF_MODE, context)
    diff = "\n".join(comparator.compare(
        prev_content.split("\n"),
        str(datetime.datetime.fromtimestamp(context["last_updated"])),
        content.split("\n"),
        str(datetime.datetime.now())))
    return diff


def _clean_part(part):
    return part.rstrip().replace("\n", common.PART_LINES_SEPARATOR)


def _apply_filters(content, input_filters, context):
    for fltcfg in input_filters or []:
        _LOG.debug("filtering by %r", fltcfg)
        flt = filters.get_filter(fltcfg, context)
        if flt:
            content = flt.filter(content)
    return content


def _load(inp_conf, gcache, output, app_args, context):
    oid = config.gen_input_oid(inp_conf)
    _LOG.debug("load: loading oid=%r", oid)
    context['name'] = config.get_input_name(inp_conf, context['_idx'])
    context['last_updated'] = gcache.get_mtime(oid)
    context['metadata'] = gcache.get_meta(oid) or {}

    loader = inputs.get_input(inp_conf, context)
    if not app_args.force and not loader.need_update():
        _LOG.info("loading '%s' - no need update", context['name'])
        return

    _LOG.info("loading '%s'...", context['name'])
    prev_content = gcache.get(oid)
    try:
        # load return list of parts
        content = loader.load()

        # filters also here - loader return generator, so exception may occur
        # during filtering
        content = _apply_filters(content, inp_conf.get('filters'), context)
        if content:
            content = "\n".join(_clean_part(part) for part in content)
        content = content or "<no data>"
    except common.NotModifiedError:
        content = prev_content

    if prev_content:
        if prev_content != content:
            diff = _gen_diff(prev_content, content, inp_conf["diff_mode"],
                             context)
            output.add_changed(inp_conf, diff, context)
            gcache.put(oid, content)
        else:
            if inp_conf.get("report_unchanged", False):
                output.add_unchanged(inp_conf, prev_content, context)
            gcache.update_mtime(oid)
    else:
        output.add_new(inp_conf, content, context)
        gcache.put(oid, content)

    # save metadata back to store
    gcache.put_meta(oid, context['metadata'])
    _LOG.debug("load: loading %r done", oid)


def _parse_options():
    parser = argparse.ArgumentParser(description='WebMon ' + VERSION)
    parser.add_argument('-i', '--inputs',
                        help='yaml file containing inputs definition'
                        ' (default inputs.yaml)')
    parser.add_argument('-c', '--config',
                        help='configuration filename (default config.yaml)')
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("-s", "--silent", action="store_true",
                        help="show only errors and warnings")
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
    return parser.parse_args()


def _show_abilities_cls(title, base_cls):
    print(title)
    for name, cls in common.get_subclasses_with_name(base_cls):
        print("  -", name)
        if hasattr(cls, "description"):
            print("    " + cls.description)
        if not hasattr(cls, "params") or not cls.params:
            continue
        print("    Parameters:")
        for param in cls.params:
            print("     - %-15s\t%-20s\tdef=%-10r\treq=%r" % param)


def _show_abilities():
    _show_abilities_cls("Inputs:", inputs.AbstractInput)
    print()
    _show_abilities_cls("Outputs:", outputs.AbstractOutput)
    print()
    _show_abilities_cls("Filters:", filters.AbstractFilter)
    print()
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
            except Exception as err:
                _LOG.error("Importing '%s' error %s", fpath, err)


def list_inputs(inps):
    print("Inputs:")
    for idx, inp_conf in enumerate(inps, 1):
        name = config.get_input_name(inp_conf, idx)
        act = "" if inp_conf.get("enable", True) else "DISABLE"
        print(" %2d '%s'" % (idx, name), act)


def update_one(args, inp, idx, defaults, output, gcache):
    # context is state object for one processing input
    context = {'_idx': idx}
    params = config.apply_defaults(defaults, inp)
    try:
        _load(params, gcache, output, args, context)
    except RuntimeError as err:
        if args.verbose:
            _LOG.exception("load %d error: %s", idx,
                            str(err).replace("\n", "; "))
        else:
            _LOG.error("load %d error: %s", idx, str(err).replace("\n", "; "))
        output.add_error(params, str(err), context)
    except Exception as err:
        _LOG.exception("load %d error: %s", idx, str(err).replace("\n", "; "))
        output.add_error(params, str(err), context)


def update(args, inps, conf, selection=None):
    start_time = time.time()

    try:
        gcache = cache.Cache(os.path.expanduser(args.cache_dir))
    except IOError:
        _LOG.warning("Init cache error")
        return

    output = outputs.OutputManager(conf.get("output"))
    if not output.valid:
        _LOG.error("no valid outputs found")
        return

    # defaults for inputs
    defaults = {
        "kind": "url",
        "diff_mode": args.diff_mode,
    }
    defaults.update(conf.get("defaults") or {})

    for idx, inp_conf in enumerate(inps, 1):
        if selection and idx not in selection:
            continue
        update_one(args, inp_conf, idx, defaults, output, gcache)

    footer = "Generate time: %.2f" % (time.time() - start_time)

    output.write(footer)
    if not selection:
        # do not delete items from cache when partial update
        gcache.delete_unused()


def main():
    args = _parse_options()

    logging_setup.logging_setup(args.log, args.verbose, args.silent)

    _load_user_classes()

    if args.abilities:
        _show_abilities()
        return

    inps = config.load_inputs(args.inputs)
    if not inps:
        _LOG.warning("No defined inputs")
        return

    if args.list_inputs:
        with config.lock():
            list_inputs(inps)
        return

    conf = config.load_configuration(args.config)
    if not conf:
        _LOG.warning("Missing configuration")
        return

    selection = None
    if args.sel:
        try:
            selection = set(int(idx.strip()) for idx in args.sel.split(","))
        except ValueError:
            _LOG.error("Invalid --sel parameter - expected numbers separated"
                       "by comma")
            return

    with config.lock():
        update(args, inps, conf, selection)


if __name__ == "__main__":
    main()
