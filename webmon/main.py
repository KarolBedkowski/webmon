#!/usr/bin/python3
"""
Main functions.
"""

import os.path
import datetime
import logging
import argparse
import imp

from . import cache
from . import config
from . import inputs
from . import logging_setup
from . import filters
from . import outputs
from . import common
from . import comparators

VERSION = "0.1"
DEFAULT_DIFF_MODE = "ndiff"

_LOG = logging.getLogger(__name__)


def _gen_diff(prev, prev_date, current, diff_mode):
    fromfiledate = str(datetime.datetime.fromtimestamp(prev_date))
    tofiledate = str(datetime.datetime.now())
    previous = prev.split("\n")
    current = current.split("\n")
    comparator = comparators.get_comparator(diff_mode or DEFAULT_DIFF_MODE)
    _LOG.debug("Using compare mode: %s", diff_mode)

    diff = "\n".join(comparator.format(
        previous, fromfiledate, current, tofiledate))
    return (diff, comparator.opts)


def _clean_part(part):
    return part.rstrip().replace("\n", common.PART_LINES_SEPARATOR)


def _load(inp, g_cache, output, force, diff_mode):
    _LOG.debug("loading %s", inp.get('name') or inp['_idx'])
    loader = inputs.get_input(inp)
    oid = loader.oid
    loader.last_updated = g_cache.get_mtime(oid)
    if loader.last_updated and not force and not loader.need_update():
        _LOG.debug("%s no need update", oid)
        return

    inp['name'] = loader.input_name
    _LOG.info("loading %s; oid=%s", inp["name"], oid)
    loader.metadata = g_cache.get_meta(oid) or {}
    prev = g_cache.get(oid)

    try:
        content = loader.load()
        # load return list of parts

        for fltcfg in inp.get('filters') or []:
            _LOG.debug("filtering by %r", fltcfg)
            flt = filters.get_filter(fltcfg)
            if flt:
                content = flt.filter(content)

        if content:
            content = "\n".join(_clean_part(part) for part in content)
        content = content or "<no data>"
    except common.NotModifiedError:
        content = prev

    if prev:
        if prev != content:
            diff, opts = _gen_diff(prev, loader.last_updated, content,
                                   inp.get("diff_mode") or diff_mode)
            output.add_changed(inp, diff, opts)
            g_cache.put(oid, content)
        else:
            if inp.get("report_unchanged", False):
                output.add_unchanged(inp, prev)
            g_cache.update_mtime(oid)
    else:
        output.add_new(inp, content)
        g_cache.put(oid, content)
    g_cache.put_meta(oid, loader.metadata)

    _LOG.debug("done")


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
    args = parser.parse_args()
    return args


def _show_abilities_cls(cls):
    if hasattr(cls, "description"):
        print("    " + cls.description)
    if not hasattr(cls, "params") or not cls.params:
        return
    print("    Parameters:")
    for param in cls.params:
        print("     - %-15s\t%-20s\tdef=%-10r\treq=%r" % param)


def _show_abilities():
    print("Inputs:")
    for name, cls in common.get_subclasses_with_name(inputs.AbstractInput):
        print("  -", name)
        _show_abilities_cls(cls)
    print()
    print("Outputs:")
    for name, cls in common.get_subclasses_with_name(outputs.AbstractOutput):
        print("  -", name)
        _show_abilities_cls(cls)
    print()
    print("Filters:")
    for name, cls in common.get_subclasses_with_name(filters.AbstractFilter):
        print("  -", name)
        _show_abilities_cls(cls)
    print()
    print("Comparators:")
    for name, cls in common.get_subclasses_with_name(
            comparators.AbstractComparator):
        print("  -", name)
        _show_abilities_cls(cls)


def _load_user_classes():
    users_scripts_dir = os.path.expanduser("~/.local/share/webmon")
    if not os.path.isdir(users_scripts_dir):
        return
    for fname in os.listdir(users_scripts_dir):
        fpath = os.path.join(users_scripts_dir, fname)
        if os.path.isfile(fpath) and fname.endswith(".py") \
                and not fname.startswith("_"):
            _LOG.debug("loading %s", fpath)
            try:
                imp.load_source(fname[:-3], fpath)
            except Exception as err:
                _LOG.error("Importing %s error %s", fpath, err)


def main():
    args = _parse_options()

    logging_setup.logging_setup(args.log, args.verbose, args.silent)

    _load_user_classes()

    if args.abilities:
        _show_abilities()
        return

    g_cache = cache.Cache(os.path.expanduser(args.cache_dir)).init()
    conf = config.load_configuration(args.config)
    inps = config.load_inputs(args.inputs)
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
            _LOG.error("load %d error: %s", idx, str(err).replace("\n", "; "))
            output.add_error(params, str(err))
        except Exception as err:
            _LOG.exception("load %d error: %s", idx,
                           str(err).replace("\n", "; "))
            output.add_error(params, str(err))

    output.write()
    g_cache.delete_unused()


if __name__ == "__main__":
    main()
