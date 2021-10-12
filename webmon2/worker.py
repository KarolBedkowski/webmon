#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2021
#
# Distributed under terms of the GPLv3 license.

"""
Background workers
"""

import datetime
import logging
import queue
import random
import re
import threading
import time

from prometheus_client import Counter

from . import common, database, filters, formatters, mailer, model, sources

_LOG = logging.getLogger(__name__)
_SOURCES_PROCESSED = Counter(
    "webmon2_sources_processed", "Sources processed count"
)
_SOURCES_PROCESSED_ERRORS = Counter(
    "webmon2_sources_processed_errors", "Sources processed with errors count"
)
_CLEANUP_INTERVAL = 60 * 60 * 24


class CheckWorker(threading.Thread):
    def __init__(self, conf, debug=False):
        threading.Thread.__init__(self, daemon=True)
        self._todo_queue = queue.Queue()
        self._conf = conf
        self._workers = conf.getint("main", "workers")
        self.debug = debug
        self.next_cleanup_start = time.time()

    def run(self):
        _LOG.info("CheckWorker started; workers: %d", self._workers)
        while True:
            time.sleep(15 if self.debug else 60)
            try:
                with database.DB.get() as db:
                    now = time.time()
                    if now > self.next_cleanup_start:
                        _delete_old_entries(db)
                        self.next_cleanup_start = now + _CLEANUP_INTERVAL

                    _LOG.debug("CheckWorker check start")
                    ids = database.sources.get_sources_to_fetch(db)
                    for id_ in ids:
                        self._todo_queue.put(id_)

                    if not self._todo_queue.empty():
                        workers = [
                            self._start_worker(idx)
                            for idx in range(min(self._workers, len(ids)))
                        ]
                        for worker in workers:
                            worker.join()

                    _LOG.debug("CheckWorker check done")
                    _send_mails(db, self._conf)
            except Exception:  # pylint: disable=broad-except
                _LOG.exception("CheckWorker thread error")

    def _start_worker(self, idx):
        worker = FetchWorker(str(idx), self._todo_queue, self._conf)
        worker.start()
        return worker


class FetchWorker(threading.Thread):
    def __init__(self, idx, todo_queue, conf):
        threading.Thread.__init__(self)
        self._idx = idx + ":" + str(id(self))
        self._todo_queue = todo_queue
        self._conf = conf

    def run(self):
        while not self._todo_queue.empty():
            source_id = self._todo_queue.get()
            with database.DB.get() as db:
                db.begin()
                try:
                    self._process_source(db, source_id)
                except Exception as err:  # pylint: disable=broad-except
                    _LOG.exception(
                        "[%s] process source %d error", self._idx, source_id
                    )
                    db.rollback()
                    source = database.sources.get(
                        db, id_=source_id, with_state=True
                    )
                    _save_state_error(db, source, err)
                finally:
                    db.commit()

    def _process_source(self, db, source_id):  # pylint: disable=no-self-use
        _SOURCES_PROCESSED.inc()
        _LOG.debug("[%s] processing source %d", self._idx, source_id)
        source = database.sources.get(db, id_=source_id, with_state=True)
        if not sources:
            _LOG.error("[%s] source %d not found!", self._idx, source_id)
            return

        try:
            src = self._get_src(db, source)
        except sources.UnknownInputException:
            _LOG.error("[%s] source %d: unknown input", self._idx, source_id)
            _save_state_error(db, source, "unsupported source")
            return

        if not src:
            return

        new_state, entries = src.load(source.state)

        if new_state.status == model.SourceStateStatus.ERROR:
            _SOURCES_PROCESSED_ERRORS.inc()
            new_state.next_update = _calc_next_check_on_error(source)
            database.sources.save_state(db, new_state, source.user_id)
            _LOG.info(
                "[%s] process source %d error: %s",
                self._idx,
                source_id,
                new_state.error,
            )
            return

        last_update = source.state.last_update or datetime.datetime.now()
        next_update = last_update + datetime.timedelta(
            seconds=common.parse_interval(source.interval)
        )
        if (
            new_state.next_update is None
            or new_state.next_update < next_update
        ):
            new_state.next_update = next_update

        if source.filters:
            entries = filters.filter_by(
                source.filters, entries, source.state, new_state, db
            )

        entries = self._final_filter_entries(entries)
        entries = self._score_entries(entries, db, source.user_id)
        entries = list(entries)
        if entries:
            max_date = max(entry.updated for entry in entries)
            new_state.set_state("last_entry_date", str(max_date))
            max_updated = max(e.updated for e in entries)
            database.entries.save_many(db, entries)
            database.groups.update_state(db, source.group_id, max_updated)
            icon = entries[0].icon
            if not new_state.icon and icon:
                new_state.icon = icon

        database.sources.save_state(db, new_state, source.user_id)

        # if source was updated - save new version
        updated_source = src.updated_source
        if updated_source:
            _LOG.debug("[%s] source %d updated", self._idx, source_id)
            database.sources.save(db, updated_source)

        _LOG.debug(
            "[%s] processing source %d FINISHED, entries=%d, state=%s",
            self._idx,
            source_id,
            len(entries),
            str(new_state),
        )

    def _final_filter_entries(self, entries):  # pylint: disable=no-self-use
        entries_oids = set()
        for entry in entries:
            entry.calculate_oid()
            if entry.oid in entries_oids:
                _LOG.debug("doubled entry %s", entry)
                continue

            entry.validate()
            entry.calculate_icon_hash()
            if entry.content:
                if not entry.content_type:
                    _LOG.warning("no content type for entry: %s", entry)
                    entry.content_type = "html"
                (
                    entry.content,
                    entry.content_type,
                ) = formatters.sanitize_content(
                    entry.content, entry.content_type
                )
            entries_oids.add(entry.oid)
            yield entry

    def _score_entries(
        self, entries: model.Entries, db, user_id: int
    ) -> model.Entries:
        # load scoring
        scss = list(self._load_scoring(db, user_id))
        if not scss:
            yield from entries
            return
        for entry in entries:
            entry.score += sum(
                score_change
                for pattern, score_change in scss
                if (entry.title and pattern.match(entry.title))
                or (entry.content and pattern.match(entry.content))
            )
            yield entry

    def _load_scoring(self, db, user_id):  # pylint: disable=no-self-use
        for scs in database.scoring.get_active(db, user_id):
            _LOG.debug("scs: %s", scs)
            try:
                cre = re.compile(
                    ".*(" + scs.pattern + ").*",
                    re.IGNORECASE | re.MULTILINE | re.DOTALL,
                )
                yield (cre, scs.score_change)
            except re.error as err:
                _LOG.warning("compile scoring pattern error: %s %s", scs, err)

    def _get_src(self, db, source):
        try:
            sys_settings = database.settings.get_dict(db, source.user_id)
            # _LOG.debug('[%s] sys_settings: %r', self._idx, sys_settings)
            if not source.interval:
                interval = sys_settings.get("interval") or "1d"
                _LOG.debug(
                    "[%s] source %d has no interval; using default: %r",
                    self._idx,
                    source.id,
                    interval,
                )
                source.interval = interval
            src = sources.get_source(source, sys_settings)
            src.validate()
            return src
        except common.ParamError as err:
            _LOG.error(
                "[%s] get source class for source id=%d error: %s",
                self._idx,
                source.id,
                err,
            )
            _save_state_error(db, source, str(err))
        return None


def _delete_old_entries(db):
    try:
        users = list(database.users.get_all(db))
        for user in users:
            db.begin()
            keep_days = database.settings.get_value(
                db, "keep_entries_days", user.id, default=90
            )
            if not keep_days:
                continue
            max_datetime = datetime.datetime.now() - datetime.timedelta(
                days=keep_days
            )
            deleted_entries, deleted_oids = database.entries.delete_old(
                db, user.id, max_datetime
            )
            _LOG.info(
                "deleted %d old entries and %d oids for user %d",
                deleted_entries,
                deleted_oids,
                user.id,
            )

            removed_bin = database.binaries.remove_unused(db, user.id)
            _LOG.info("removed %d binaries for user %d", removed_bin, user.id)
            db.commit()

        db.begin()
        states, entries = database.binaries.clean_sources_entries(db)
        _LOG.info("cleaned %d source states and %d entries", states, entries)
        db.commit()
    except Exception as err:  # pylint: disable=broad-except
        _LOG.exception("delete old error: %s", err)


def _send_mails(db, conf):
    if not conf.getboolean("smtp", "enabled", failback=False):
        return

    _LOG.debug("_send_mails start")
    users = list(database.users.get_all(db))
    for user in users:
        db.begin()
        try:
            mailer.process(db, user, conf)
        except Exception:  # pylint: disable=broad-except
            _LOG.exception("send mail error")
            db.rollback()
        else:
            db.commit()

    _LOG.debug("_send_mails end")


def _calc_next_check_on_error(source: model.Source):
    next_check_delta = common.parse_interval(source.interval or "1d")
    # add some random time
    next_check_delta += random.randint(3600, 7200)
    return datetime.datetime.now() + datetime.timedelta(
        seconds=next_check_delta
    )


def _save_state_error(db, source: model.Source, err: str):
    _SOURCES_PROCESSED_ERRORS.inc()
    assert source.state

    new_state = source.state.new_error(str(err))
    new_state.next_update = _calc_next_check_on_error(source)

    database.sources.save_state(db, new_state, source.user_id)
