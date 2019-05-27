#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright (c) Karol Będkowski, 2016-2019
#
# Distributed under terms of the GPLv3 license.

"""
Background workers
"""

import queue
import time
import threading
import logging
import datetime
import random
from prometheus_client import Counter

from . import sources, common, filters, database, model, formatters, mailer

_LOG = logging.getLogger(__name__)
_SOURCES_PROCESSED = Counter(
    "webmon2_sources_processed", "Sources processed count")
_SOURCES_PROCESSED_ERRORS = Counter(
    "webmon2_sources_processed_errors",
    "Sources processed with errors count")
_CLEANUP_INTERVAL = 60 * 60 * 24


class CheckWorker(threading.Thread):
    def __init__(self, workers=2, debug=False):
        threading.Thread.__init__(self, daemon=True)
        self._todo_queue = queue.Queue()
        self._workers = workers
        self.debug = debug
        self.next_cleanup_start = time.time()

    def run(self):
        _LOG.info("CheckWorker started; workers: %d", self._workers)
        while True:
            time.sleep(15 if self.debug else 60)
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
                    workers = [self._start_worker(idx) for idx
                               in range(min(self._workers, len(ids)))]
                    for worker in workers:
                        worker.join()

                _LOG.debug("CheckWorker check done")
                _send_mails(db)

    def _start_worker(self, idx):
        worker = FetchWorker(str(idx), self._todo_queue)
        worker.start()
        return worker


class FetchWorker(threading.Thread):
    def __init__(self, idx, todo_queue):
        threading.Thread.__init__(self)
        self._idx = idx + ":" + str(id(self))
        self._todo_queue = todo_queue

    def run(self):
        while not self._todo_queue.empty():
            source_id = self._todo_queue.get()
            with database.DB.get() as db:
                try:
                    self._process_source(db, source_id)
                    db.commit()
                except Exception:  # pylint: disable=broad-except
                    _LOG.exception("[%s] process source %d error", self._idx,
                                   source_id)
                    db.rollback()

    def _process_source(self, db, source_id):  # pylint: disable=no-self-use
        _SOURCES_PROCESSED.inc()
        _LOG.debug("[%s] processing source %d", self._idx, source_id)
        try:
            source = database.sources.get(db, id_=source_id, with_state=True)
        except database.NotFound:
            _LOG.error("[%s] source %d not found!", self._idx, source_id)
            return

        src = self._get_src(db, source)
        if not src:
            return

        try:
            new_state, entries = src.load(source.state)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("[%s] load source id=%d error: %s",
                           self._idx, source_id, err)
            _save_state_error(db, source, err)
            return

        last_update = source.state.last_update or datetime.datetime.now()
        next_update = last_update + datetime.timedelta(
            seconds=common.parse_interval(source.interval))
        if new_state.next_update is None \
                or new_state.next_update < next_update:
            new_state.next_update = next_update

        db.begin()

        if source.filters:
            entries = filters.filter_by(source.filters, entries,
                                        source.state, new_state, db)

        entries = list(self._final_filter_entries(entries))
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

        _LOG.debug("[%s] processing source %d FINISHED, entries=%d, state=%s",
                   self._idx, source_id, len(entries), str(new_state))

    def _final_filter_entries(self, entries):  # pylint: disable=no-self-use
        entries_oids = set()
        for entry in entries:
            entry.calculate_oid()
            if entry.oid in entries_oids:
                _LOG.debug("doubled entry %s", entry)
                continue

            entry.validate()
            entry.calculate_icon_hash()
            content_type = entry.get_opt("content-type")
            entry.content = formatters.sanitize_content(
                entry.content, content_type)
            entries_oids.add(entry.oid)
            yield entry

    def _get_src(self, db, source):
        try:
            sys_settings = database.settings.get_dict(
                db, source.user_id)
            # _LOG.debug('[%s] sys_settings: %r', self._idx, sys_settings)
            if not source.interval:
                interval = sys_settings.get('interval') or '1d'
                _LOG.debug("[%s] source %d has no interval; using default: %r",
                           self._idx, source.id, interval)
                source.interval = interval
            src = sources.get_source(source, sys_settings)
            src.validate()
            return src
        except common.ParamError as err:
            _LOG.error("[%s] get source class for source id=%d error: %s",
                       self._idx, source.id, err)
            _save_state_error(db, source, str(err))
        return None


def _delete_old_entries(db):
    try:
        users = list(database.users.get_all(db))
        for user in users:
            db.begin()
            keep_days = database.settings.get_value(
                db, 'keep_entries_days', user.id, default=90)
            if not keep_days:
                continue
            max_datetime = datetime.datetime.now() - \
                datetime.timedelta(days=keep_days)
            deleted_entries, deleted_oids = database.entries.delete_old(
                db, user.id, max_datetime)
            _LOG.info("deleted %d old entries and %d oids for user %d",
                      deleted_entries, deleted_oids, user.id)

            removed_bin = database.binaries.remove_unused(db, user.id)
            _LOG.info("removed %d binaries for user %d", removed_bin,
                      user.id)
            db.commit()
        db.begin()
        states, entries = database.binaries.clean_sources_entries(db)
        _LOG.info("cleaned %d source states and %d entries", states, entries)
        db.commit()
    except Exception as err:  # pylint: disable=broad-except
        _LOG.exception("delete old error: %s", err)


def _send_mails(db):
    _LOG.debug("_send_mails start")
    users = list(database.users.get_all(db))
    for user in users:
        db.begin()
        try:
            mailer.process(db, user.id)
        except Exception:  # pylint: disable=broad-except
            _LOG.exception("send mail error")
            db.rollback()
        else:
            db.commit()
    _LOG.debug("_send_mails end")


def _save_state_error(db, source: model.Source, err: str):
    _SOURCES_PROCESSED_ERRORS.inc()
    next_check_delta = common.parse_interval(source.interval or '1d')
    # add some random time
    next_check_delta += random.randint(600, 3600)

    new_state = source.state.new_error(str(err))
    new_state.next_update = datetime.datetime.now() + \
        datetime.timedelta(seconds=next_check_delta)

    database.sources.save_state(db, new_state, source.user_id)
