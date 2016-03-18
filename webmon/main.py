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


def _gen_diff(prev, prev_date, current, diff_mode, context):
    fromfiledate = str(datetime.datetime.fromtimestamp(prev_date))
    tofiledate = str(datetime.datetime.now())
    previous = prev.split("\n")
    current = current.split("\n")
    comparator = comparators.get_comparator(
        diff_mode or DEFAULT_DIFF_MODE, context)
    _LOG.debug("Using compare mode: %s", diff_mode)

    diff = "\n".join(comparator.format(
        previous, fromfiledate, current, tofiledate))
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


def _load(inp, gcache, output, force, diff_mode, context):
    _LOG.debug("loading %s", inp.get('name') or str(context['_idx']))

    loader = inputs.get_input(inp, context)
    oid, name = loader.oid, loader.input_name
    context['last_updated'] = last_updated = gcache.get_mtime(oid)
    if last_updated and not force and not loader.need_update():
        _LOG.debug("%s no need update", oid)
        return

    context['metadata'] = gcache.get_meta(oid) or {}
    prev = gcache.get(oid)

    _LOG.info("loading %s; oid=%s", name, oid)
    try:
        # load return list of parts
        content = loader.load()
        content = _apply_filters(content, inp.get('filters'), context)
        if content:
            content = "\n".join(_clean_part(part) for part in content)
        content = content or "<no data>"
    except common.NotModifiedError:
        content = prev

    if prev:
        if prev != content:
            diff = _gen_diff(prev, loader.last_updated, content,
                             inp.get("diff_mode") or diff_mode, context)
            output.add_changed(inp, diff, context)
            gcache.put(oid, content)
        else:
            if inp.get("report_unchanged", False):
                output.add_unchanged(inp, prev, context)
            gcache.update_mtime(oid)
    else:
        output.add_new(inp, content, context)
        gcache.put(oid, content)

    gcache.put_meta(oid, context['metadata'])
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


def _show_abilities_cls(name, cls):
    print("  -", name)
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
        _show_abilities_cls(name, cls)
    print()
    print("Outputs:")
    for name, cls in common.get_subclasses_with_name(outputs.AbstractOutput):
        _show_abilities_cls(name, cls)
    print()
    print("Filters:")
    for name, cls in common.get_subclasses_with_name(filters.AbstractFilter):
        _show_abilities_cls(name, cls)
    print()
    print("Comparators:")
    for name, cls in common.get_subclasses_with_name(
            comparators.AbstractComparator):
        _show_abilities_cls(name, cls)


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

    inps = config.load_inputs(args.inputs)
    if not inps:
        _LOG.warning("No defined inputs")
        return

    conf = config.load_configuration(args.config)
    if not conf:
        _LOG.warning("Missing configuration")
        return

    try:
        gcache = cache.Cache(os.path.expanduser(args.cache_dir))
    except IOError:
        _LOG.warning("Init cache error")
        return

    output = outputs.Output(conf.get("output"))
    if not output.valid:
        _LOG.error("no valid outputs found")
        return

    # defaults for inputs
    defaults = {"kind": "url"}
    defaults.update(conf.get("defaults"))

    for idx, inp in enumerate(inps):
        # context is state object for one processing input
        context = {'_idx': idx + 1}
        params = config.apply_defaults(defaults, inp)
        try:
            _load(params, gcache, output, args.force, args.diff_mode, context)
        except RuntimeError as err:
            _LOG.error("load %d error: %s", idx, str(err).replace("\n", "; "))
            output.add_error(params, str(err), context)
        except Exception as err:
            _LOG.exception("load %d error: %s", idx,
                           str(err).replace("\n", "; "))
            output.add_error(params, str(err), context)

    output.write()
    gcache.delete_unused()


if __name__ == "__main__":
    main()
