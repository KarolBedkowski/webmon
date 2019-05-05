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

from . import sources, common, filters, database, model

_LOG = logging.getLogger("main")
_SOURCES_PROCESSED = Counter(
    "webmon2_sources_processed", "Sources processed count")
_SOURCES_PROCESSED_ERRORS = Counter(
    "webmon2_sources_processed_errors",
    "Sources processed with errors count")


class CheckWorker(threading.Thread):
    def __init__(self, workers=2):
        threading.Thread.__init__(self, daemon=True)
        self._todo_queue = queue.Queue()
        self._workers = workers

    def run(self):
        cntr = 0
        with database.DB.get() as db:
            _LOG.info("CheckWorker started; workers: %d", self._workers)
            while True:
                if not cntr:
                    _delete_old_entries(db)
                cntr = (cntr + 1) % 60
                _LOG.debug("CheckWorker check start")
                if self._todo_queue.empty():
                    ids = database.sources.get_sources_to_fetch(db)
                    for id_ in ids:
                        self._todo_queue.put(id_)

                if not self._todo_queue.empty():
                    workers = []
                    for _ in range(self._workers):
                        worker = FetchWorker(self._todo_queue)
                        worker.start()
                        workers.append(worker)

                    for worker in workers:
                        worker.join()

                _LOG.debug("CheckWorker check done")
                time.sleep(60)


class FetchWorker(threading.Thread):
    def __init__(self, todo_queue):
        threading.Thread.__init__(self)
        self._todo_queue = todo_queue

    def run(self):
        with database.DB.get() as db:
            while not self._todo_queue.empty():
                source_id = self._todo_queue.get()
                try:
                    self._process_source(db, source_id)
                except Exception:  # pylint: disable=broad-except
                    _LOG.exception("process source %d error", source_id)

    def _process_source(self, db, source_id):  # pylint: disable=no-self-use
        _SOURCES_PROCESSED.inc()
        _LOG.info("processing source %d", source_id)
        try:
            source = database.sources.get(db, id_=source_id, with_state=True)
        except database.NotFound:
            _LOG.error("source %d not found!", source_id)
            return
        try:
            sys_settings = database.settings.get_dict(
                db, source.user_id)
            _LOG.debug('sys_settings: %r', sys_settings)
            if not source.interval:
                interval = sys_settings.get('interval') or '1d'
                _LOG.debug("source %d has no interval; using default: %r",
                           source.id, interval)
                source.interval = interval
            src = sources.get_source(source, sys_settings)
            src.validate()
        except common.ParamError as err:
            _LOG.error("get cource class for source id=%d error: %s",
                       source_id, err)
            _save_state_error(db, source, str(err))
            return
        if not src:
            return

        try:
            new_state, entries = src.load(source.state)
        except Exception as err:  # pylint: disable=broad-except
            _LOG.exception("load source id=%d error: %s", source_id, err)
            _save_state_error(db, source, err)
            return

        if new_state.next_update is None:
            last_update = source.state.last_update or datetime.datetime.now()
            new_state.next_update = last_update + \
                datetime.timedelta(
                    seconds=common.parse_interval(source.interval))

        if source.filters:
            entries = filters.filter_by(source.filters, entries,
                                        source.state, new_state)

        entries = list(entry for entry in entries if entry.calculate_oid())

        for entry in entries:
            entry.validate()

        database.entries.save_many(db, entries, source_id)
        database.sources.save_state(db, new_state)
        _LOG.info("processing source %d FINISHED, entries=%d, state=%s",
                  source_id, len(entries), str(new_state))


def _delete_old_entries(db):
    users = list(database.users.get_all(db))
    for user in users:
        keep_days = database.settings.get_value(
            db, 'keep_entries_days', user.id, default=90)
        if not keep_days:
            continue
        max_datetime = datetime.datetime.now() - \
            datetime.timedelta(days=keep_days)
        database.entries.delete_old(db, user.id, max_datetime)


def _save_state_error(db, source: model.Source, err: str):
    _SOURCES_PROCESSED_ERRORS.inc()
    next_check_delta = common.parse_interval(source.interval or '1d')
    # add some random time
    next_check_delta += random.randint(600, 3600)
    new_state = source.state.new_error(str(err))
    new_state.next_update = datetime.datetime.now() + \
        datetime.timedelta(seconds=next_check_delta)
    database.sources.save_state(db, new_state)
