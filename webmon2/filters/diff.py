#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Text difference filters.
"""
import difflib
import logging
import typing as ty

from webmon2 import common, model, database

from ._abstract import AbstractFilter

_LOG = logging.getLogger(__name__)

_ = ty


class NDiff(AbstractFilter):
    """Compare text with previous version (in state)."""

    name = "ndiff"
    short_info = "Diff with previous content"
    long_info = "Compare current and previous content; show changed elements"
    params = [
        common.SettingDef(
            "threshold",
            "Skip elements when changes percent is below this level",
            default=0.1),
        common.SettingDef(
            "min_changed",
            "Skip elements when changes lines is below this level",
            default=1),
    ]  # type: ty.List[common.SettingDef]

    def validate(self):
        super().validate()
        threshold = self._conf.get("threshold")
        if not isinstance(threshold, (float, int)) \
                or threshold < 0 or threshold > 1:
            raise common.ParamError("invalid threshold : %r" % threshold)

    def filter(self, entries: model.Entries, prev_state: model.SourceState,
               curr_state: model.SourceState) -> model.Entries:
        if not entries:
            return
        try:
            entry = next(entries)
        except StopIteration:
            return
        if not entry.content:
            return

        filter_state = None
        with database.DB.get() as db:
            filter_state = database.sources.get_filter_state(
                db, curr_state.source_id, self.name)
        prev_content = filter_state.get('content') if filter_state else None

        if not prev_content:
            entry = entry.clone()
            entry.status = 'new'
            entry.set_opt('preformated', True)
            entry.set_opt("content-type", "plain")
            yield entry
            return

        old_lines = prev_content.split('\n')
        new_lines = entry.content.split('\n')
        res = list(difflib.ndiff(old_lines, new_lines))

        changed_lines = sum(1 for line in res if line and line[0] != ' ')
        if not _check_changes(changed_lines, len(old_lines),
                              self._conf.get("threshold"),
                              self._conf.get("min_changed")):
            return

        filter_state = {'content': entry.content}
        with database.DB.get() as db:
            database.sources.put_filter_state(
                db, curr_state.source_id, self.name, filter_state)

        entry = entry.clone()
        entry.status = 'new'
        entry.content = '\n'.join(res)
        entry.set_opt("content-type", "preformated")
        entry.set_opt('_ndiff_changed_lines', changed_lines)
        entry.set_opt('_ndiff_old_lines', len(old_lines))
        yield entry

    def _filter(self, entry: model.Entry) -> model.Entries:
        pass


def _check_changes(changed_lines: int, old_lines: int,
                   changes_th, min_changed) -> bool:
    if not changed_lines:
        return False

    if changes_th and old_lines:
        changes = float(changed_lines) / old_lines
        _LOG.debug("changes: %d / %d (%f %%)", changed_lines, old_lines,
                   changes)
        if changes < changes_th:
            _LOG.info("changes not above threshold (%f<%f)", changes,
                      changes_th)
            return False

    if min_changed and old_lines:
        _LOG.debug("changes: %f", changed_lines)
        if changed_lines < min_changed:
            _LOG.info("changes not above minimum (%d<%d)", changed_lines,
                      min_changed)
            return False

    return True
