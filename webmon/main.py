#!/usr/bin/python3

import os.path
import difflib
import datetime
import logging
import argparse
import copy

from . import cache
from . import config
from . import inputs
from . import logging_setup
from . import filters
from . import outputs


_LOG = logging.getLogger(__name__)


def _load(inp, g_cache, output):
    _LOG.debug("loading %s", inp['name'])
    loader = inputs.get_input(inp)
    oid = loader.get_oid()
    last = g_cache.get_mtime(oid)
    if last and not loader.need_update(last):
        _LOG.debug("no need update")
        return

    inp['_input_name'] = loader.input_name
    _LOG.info("loading %s; oid=%s", inp["_input_name"], oid)
    content = loader.load(last)

    for fltcfg in inp.get('filters') or []:
        _LOG.debug("filtering by %r", fltcfg)
        flt = filters.get_filter(fltcfg)
        if flt:
            content = flt.filter(content)

    content = "\n".join(content) or "<no data>"

    prev = g_cache.get(oid)
    if prev:
        if prev != content:
            diff = '\n'.join(difflib.unified_diff(
                prev.split("\n"), content.split("\n"),
                fromfiledate=str(datetime.datetime.fromtimestamp(last)),
                tofiledate=str(datetime.datetime.now()),
                n=2, lineterm='\n'))
            output.add_changed(inp, diff)
        else:
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
    parser.add_argument('--log',
                        help='log file name')
    parser.add_argument('--cache-dir',
                        default="~/.cache/webmon/cache",
                        help='path to cache directory')
    args = parser.parse_args()
    return args


def main():
    args = _parse_options()
    logging_setup.logging_setup(args.log, args.verbose)

    g_cache = cache.Cache(os.path.expanduser(args.cache_dir))
    conf = config.load_configuration(os.path.expanduser(args.config))
    inps = config.load_inputs(os.path.expanduser(args.inputs))
    output = outputs.Output(conf.get("output"))

    defaults = conf.get("defaults") or {}
    if 'kind' in defaults:
        del defaults['kind']

    for idx, inp in enumerate(inps):
        params = copy.deepcopy(defaults)
        params.update(inp)
        if not params.get("name"):
            params["name"] = str(idx + 1)
        params['_input_name'] = params["name"]
        try:
            _load(params, g_cache, output)
        except RuntimeError as err:
            _LOG.error("load error: %s", str(err).replace("\n", "; "))
            output.add_error(params, str(err))

    output.write()


if __name__ == "__main__":
    main()
