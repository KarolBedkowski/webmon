#!/usr/bin/python3

import difflib
import datetime

import cache
import config
import input
import logging_setup
import filters
import reporter


def main():
    logging_setup.logging_setup("webmon.log", __debug__)

    g_cache = cache.Cache("cache")
    conf = config.load_configuration("config.yaml")
    inps = config.load_inputs("urls.yaml")
    reps = []
    for repname, repconf in (conf.get("reporters") or {}).items():
        rep = reporter.get_reporter(repname, repconf)
        if rep:
            rep.begin()
            reps.append(rep)

    for idx, inp in enumerate(inps):
        try:
            if not inp.get("name"):
                inp["name"] = str(idx + 1)
            loader = input.get_input(inp)
            oid = input.get_oid(inp)
            last = g_cache.get_mtime(oid)
            content = loader(inp, last)
            prev = g_cache.get(oid)

            for fltcfg in inp.get('filters') or []:
                flt = filters.get_filter(fltcfg)
                content = flt(content, **fltcfg)

            if prev:
                if prev != content:
                    diff = '\n'.join(difflib.unified_diff(
                        prev.split("\n"), content.split("\n"),
                        fromfiledate=str(
                            datetime.datetime.fromtimestamp(last)),
                        tofiledate=str(datetime.datetime.now()),
                        n=2, lineterm='\n'))
                    for rep in reps:
                        rep.report_changed(inp, diff)
                else:
                    for rep in reps:
                        rep.report_unchanged(inp)
            else:
                for rep in reps:
                    rep.report_new(inp)

            g_cache.put(oid, content)
        except RuntimeError as err:
            for rep in reps:
                rep.report_error(inp, str(err))

    for rep in reps:
        rep.end()


if __name__ == "__main__":
    main()
