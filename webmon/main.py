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
PARTS_SEP = "\n\n-----\n\n"

_LOG = logging.getLogger("main")


def _compare(prev_content, content, inp_conf):
    comparator = comparators.get_comparator(
        inp_conf["diff_mode"] or DEFAULT_DIFF_MODE, inp_conf)
    diff = "\n".join(comparator.compare(
        prev_content.split("\n"),
        str(datetime.datetime.fromtimestamp(inp_conf["_last_updated"])),
        content.split("\n"),
        str(datetime.datetime.now())))
    return diff


def _check_last_error_time(inp_conf):
    """
    Check if recovered file may be useful.

    Return true when load error occurred and still `on_error_wait` interval
    not pass.
    """
    last_error = inp_conf['_metadata'].get('last_error')
    if last_error:
        on_error_wait = inp_conf['on_error_wait']
        if on_error_wait:
            on_error_wait = common.parse_interval(on_error_wait)
            return time.time() < last_error + on_error_wait
    return False


def _is_recovery_accepted(mtime, inp_conf, last_updated):
    """Check is recovered file is valid by modified time.

    :param mtime: timestamp of recovered file
    :param inp_conf: source configuration
    :param last_updated: last updated valid file
    """
    interval = common.parse_interval(inp_conf['interval'])
    if last_updated:
        return last_updated + interval < mtime
    # no previous valid file found
    return time.time() - mtime < interval


def _load_content(loader, inp_conf, debug):
    start = time.time()
    # load list of parts
    parts = loader.load()
    if debug:
        parts = list(parts)
        _LOG.debug("Loaded: %s", pprint.saferepr(parts))

    # apply filters
    for fltcfg in inp_conf.get('filters') or []:
        _LOG.debug("filtering by %r", fltcfg)
        flt = filters.get_filter(fltcfg, inp_conf)
        if flt:
            parts = flt.filter(parts)
            if debug:
                parts = list(parts)
                _LOG.debug("Filtered by %s: %s", flt, pprint.saferepr(parts))

    content = None
    if parts:
        content = PARTS_SEP.join(ppart for ppart in
                                 (part.rstrip() for part in parts)
                                 if ppart)
    content = content or "<no data>"
    if debug:
        _LOG.debug("Result: %s", pprint.saferepr(content))
    inp_conf['_debug']['load_time'] = time.time() - start
    return content, inp_conf


def _clean_meta_on_success(inp_conf):
    meta = inp_conf['_metadata']
    if 'last_error' in meta:
        del meta['last_error']
    if 'last_error_msg' in meta:
        del meta['last_error_msg']
    return inp_conf


def _add_to_output(output, prev_content, content, inp_conf):
    oid = inp_conf['_oid']
    if prev_content is None:
        # new content
        _LOG.debug("load: loading oid=%r - new content", oid)
        output.add_new(inp_conf, content)
    elif prev_content != content:
        # changed content
        _LOG.debug("load: loading oid=%r - changed content", oid)
        diff = _compare(prev_content, content, inp_conf)
        output.add_changed(inp_conf, diff)
    else:
        _LOG.debug("load: loading oid=%r - unchanged content", oid)
        if inp_conf.get("report_unchanged", False):
            # unchanged content, but report
            output.add_unchanged(inp_conf, prev_content)


def _try_recover(inp_conf, gcache):
    """Try recover content & metadata; if not success - load last metadata."""
    oid = inp_conf['_oid']
    recovered = False
    last_updated = gcache.get_mtime(oid)
    content, mtime, meta = gcache.get_recovered(oid)
    if content is not None \
            and _is_recovery_accepted(mtime, inp_conf, last_updated):
        recovered = True
        inp_conf['_last_updated'] = mtime
        inp_conf['_metadata'] = meta or {}
        _LOG.info("loading '%s' - recovered", inp_conf['_name'])
    else:
        inp_conf['_last_updated'] = last_updated
        inp_conf['_metadata'] = gcache.get_meta(oid) or {}
    return recovered, content, inp_conf


def _load(inp_conf, gcache, output, app_args):
    oid = inp_conf['_oid']
    _LOG.debug("load: loading oid=%r", oid)

    # try to recover, load meta
    recovered, content, inp_conf = _try_recover(inp_conf, gcache)

    if not app_args.force and _check_last_error_time(inp_conf):
        _LOG.info("loading '%s' - skipping - still waiting after error",
                  inp_conf['_name'])
        return False

    loader = inputs.get_input(inp_conf)
    if not app_args.force and not loader.need_update() and not recovered:
        _LOG.info("loading '%s' - no need update", inp_conf['_name'])
        return False

    prev_content = gcache.get(oid)
    if not recovered:
        _LOG.info("loading '%s'...", inp_conf['_name'])
        try:
            content, inp_conf = _load_content(loader, inp_conf, app_args.debug)
        except common.NotModifiedError:
            content = prev_content
        except common.InputError as err:
            inp_conf['_metadata']['last_error'] = time.time()
            inp_conf['_metadata']['last_error_msg'] = str(err)
            gcache.put_meta(oid, inp_conf['_metadata'])
            raise

    inp_conf = _clean_meta_on_success(inp_conf)
    if app_args.debug:
        _LOG.debug("diff prev: %s", pprint.saferepr(prev_content))
        _LOG.debug("diff content: %s", pprint.saferepr(content))
    _add_to_output(output, prev_content, content, inp_conf)
    gcache.put(oid, content)
    gcache.put_meta(oid, inp_conf['_metadata'])
    _LOG.debug("load: loading %r done", oid)
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
            except ImportError as err:
                _LOG.error("Importing '%s' error %s", fpath, err)


def _list_inputs(inps, debug):
    print("Inputs:")
    for idx, inp_conf in enumerate(inps, 1):
        inp_conf['_idx'] = idx
        name = config.get_input_name(inp_conf)
        act = "" if inp_conf.get("enable", True) else "DISABLE"
        oid = config.gen_input_oid(inp_conf) if debug else ""
        print(" %2d %-40s" % (idx, name), act, oid)


def _update_one(args, inp_conf, output, gcache):
    try:
        return _load(inp_conf, gcache, output, args)
    except RuntimeError as err:
        if args.debug:
            _LOG.exception("load %d error: %s", inp_conf['_idx'],
                           str(err).replace("\n", "; "))
        else:
            _LOG.error("load %d error: %s", inp_conf['_idx'],
                       str(err).replace("\n", "; "))
        output.add_error(inp_conf, str(err))
    except Exception as err:
        _LOG.exception("load %d error: %s", inp_conf['_idx'],
                       str(err).replace("\n", "; "))
        output.add_error(inp_conf, str(err))
    return True


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
    defaults = {}
    defaults.update(config.DEFAULTS)
    defaults.update(conf.get("defaults") or {})
    defaults["diff_mode"] = args.diff_mode

    processed = 0

    for idx, inp_conf in enumerate(inps, 1):
        if selection and idx not in selection:
            continue
        params = config.apply_defaults(defaults, inp_conf)
        params['_opt'] = {}
        params['_debug'] = {}
        params['_idx'] = idx
        params['_name'] = config.get_input_name(params)
        params['_oid'] = config.gen_input_oid(inp_conf)
        if _update_one(args, params, output, gcache):
            processed += 1

    duration = time.time() - start_time
    footer = "Generate time: %.2f" % duration

    output.write(footer)
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
        _LOG.error("No defined inputs")
        return

    if args.list_inputs:
        with config.lock():
            _list_inputs(inps, args.debug)
        return

    conf = config.load_configuration(args.config)
    if not conf:
        _LOG.error("Missing configuration")
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
