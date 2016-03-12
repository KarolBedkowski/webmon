#!/usr/bin/python3
"""
Main functions.
"""

import os.path
import datetime
import logging
import argparse

from . import cache
from . import config
from . import inputs
from . import logging_setup
from . import filters
from . import outputs
from . import common
from . import comparators


_LOG = logging.getLogger(__name__)


def _gen_diff(prev, prev_date, current, diff_mode):
    fromfiledate = str(datetime.datetime.fromtimestamp(prev_date))
    tofiledate = str(datetime.datetime.now())

    diff_mode = diff_mode or "ndiff"

    previous = prev.split("\n\n")
    current = current.split("\n\n")

    return comparators.get_comparator(diff_mode)(previous, fromfiledate,
                                                 current, tofiledate)


def _load(inp, g_cache, output, force, diff_mode):
    _LOG.debug("loading %s", inp.get('name') or inp['_idx'])
    loader = inputs.get_input(inp)
    oid = loader.get_oid()
    last = g_cache.get_mtime(oid)
    if last and not force and not loader.need_update(last):
        _LOG.debug("no need update")
        return

    inp['name'] = loader.input_name
    _LOG.info("loading %s; oid=%s", inp["name"], oid)
    try:
        content = loader.load(last)
    except common.NotModifiedError:
        content = last
    else:
        for fltcfg in inp.get('filters') or []:
            _LOG.debug("filtering by %r", fltcfg)
            flt = filters.get_filter(fltcfg)
            if flt:
                content = flt.filter(content)

        content = "\n\n".join(content) or "<no data>"

    prev = g_cache.get(oid)
    if prev:
        if prev != content:
            diff = _gen_diff(prev, last, content,
                             inp.get("diff_mode") or diff_mode)
            output.add_changed(inp, "\n".join(diff))
            g_cache.put(oid, content)
        else:
            if inp.get("report_unchanged", False):
                output.add_unchanged(inp)
            g_cache.update_mtime(oid)
    else:
        output.add_new(inp, content)
        g_cache.put(oid, content)

    _LOG.debug("done")


def _parse_options():
    parser = argparse.ArgumentParser(description='WebMon')
    parser.add_argument('-i', '--inputs',
                        help='yaml file containing inputs definition',
                        default="inputs.yaml")
    parser.add_argument('-c', '--config',
                        default="config.yaml",
                        help='configuration filename')
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
    args = parser.parse_args()
    return args


def main():
    args = _parse_options()
    logging_setup.logging_setup(args.log, args.verbose, args.silent)

    g_cache = cache.Cache(os.path.expanduser(args.cache_dir)).init()
    conf = config.load_configuration(os.path.expanduser(args.config))
    inps = config.load_inputs(os.path.expanduser(args.inputs))
    if not g_cache or not conf or not inps:
        return

    output = outputs.Output(conf.get("output"))
    if not output.valid:
        _LOG.error("no valid outputs found")
        return

    # defaults for inputs
    defaults = conf.get("defaults") or {}
    if 'kind' not in defaults:
        defaults['kind'] = "url"

    for idx, inp in enumerate(inps):
        params = config.apply_defaults(defaults, inp)
        params["_idx"] = str(idx + 1)
        try:
            _load(params, g_cache, output, args.force, args.diff_mode)
        except RuntimeError as err:
            _LOG.error("load error: %s", str(err).replace("\n", "; "))
            output.add_error(params, str(err))

    output.write()
    g_cache.delete_unused()


if __name__ == "__main__":
    main()
