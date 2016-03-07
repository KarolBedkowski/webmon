#!/usr/bin/python3

import difflib
import datetime
import logging

import cache
import config
import input
import logging_setup
import filters
import outputs


_LOG = logging.getLogger(__name__)


def _load(inp, g_cache, output):
    loader = input.get_input(inp)
    oid = loader.get_oid()
    last = g_cache.get_mtime(oid)
    content = loader.load(last)

    for fltcfg in inp.get('filters') or []:
        flt = filters.get_filter(fltcfg)
        if flt:
            content = flt.filter(content)

    prev = g_cache.get(oid)
    if prev:
        if prev != content:
            diff = '\n'.join(difflib.unified_diff(
                prev.split("\n"), content.split("\n"),
                fromfiledate=str(datetime.datetime.fromtimestamp(last)),
                tofiledate=str(datetime.datetime.now()),
                n=2, lineterm='\n'))
            output.report_changed(inp, diff)
        else:
            output.report_unchanged(inp)
            g_cache.update_mtime(oid)
    else:
        output.report_new(inp, content)

    g_cache.put(oid, content)


def main():
    logging_setup.logging_setup("webmon.log", __debug__)

    g_cache = cache.Cache("cache")
    conf = config.load_configuration("config.yaml")
    inps = config.load_inputs("urls.yaml")
    output = outputs.Output(conf.get("output"))

    for idx, inp in enumerate(inps):
        if not inp.get("name"):
            inp["name"] = str(idx + 1)
        try:
            _load(inp, g_cache, output)
        except RuntimeError as err:
            _LOG.exception("load error: %s", err)
            output.report_error(inp, str(err))

    output.end()


if __name__ == "__main__":
    main()
