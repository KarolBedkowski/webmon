#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019  <@K-HP>
#
# Distributed under terms of the GPLv3 license.

"""

"""

import queue
import time
import threading
import logging
import datetime
import random

from . import inputs, common, filters, database

_LOG = logging.getLogger("main")


class CheckWorker(threading.Thread):
    def __init__(self, workers=4):
        # TODO: param workers
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
                    ids = db.get_sources_to_fetch()
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
                self._process_source(db, source_id)

    def _process_source(self, db, source_id):
        _LOG.info("processing source %d", source_id)
        try:
            source = db.get_source(id_=source_id, with_state=True)
        except database.NotFound:
            _LOG.error("source %d not found!", source_id)
            return
        try:
            sys_settings = db.get_settings_map(source.user_id)
            _LOG.debug('sys_settings: %r', sys_settings)
            inp = inputs.get_input(source, sys_settings)
            inp.validate()
        except common.ParamError as err:
            _LOG.error("get input for source id=%d error: %s", source_id, err)
            _save_state_error(db, source, err)
            return
        if not inp:
            return

        try:
            new_state, entries = inp.load(source.state)
        except Exception as err:
            _LOG.exception("load source id=%d error: %s", source_id, err)
            _save_state_error(db, source, err)
            return

        if new_state.next_update is None:
            last_update = source.state.last_update or datetime.datetime.now()
            new_state.next_update = last_update + \
                datetime.timedelta(
                    seconds=common.parse_interval(source.interval))

        if source.filters:
            entries, new_state = filters.filter_by(source.filters, entries,
                                                   source.state, new_state)

        for entry in entries:
            entry.calculate_oid()

        db.insert_entries(entries)
        db.save_state(new_state)
        _LOG.info("processing source %d FINISHED, entries=%d, state=%s",
                  source_id, len(entries), str(new_state))


def _delete_old_entries(db):
    users = list(db.get_users())
    for user in users:
        keep_days = db.get_setting_value('keep_entries_days', user.id,
                                         default=90)
        if not keep_days:
            continue
        max_datetime = datetime.datetime.now() - \
            datetime.timedelta(days=keep_days)
        db.delete_old_entries(user.id, max_datetime)


def _save_state_error(db, source, err):
    next_check_delta = common.parse_interval(source.interval or '1d')
    # add some random time
    next_check_delta += random.randint(600, 3600)
    new_state = source.state.new_error(str(err))
    new_state.next_update = datetime.datetime.now() + \
        datetime.timedelta(seconds=next_check_delta)
    db.save_state(new_state)
