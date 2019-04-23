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

from . import inputs, common, filters

_LOG = logging.getLogger("main")


class CheckWorker(threading.Thread):
    def __init__(self, db):
        threading.Thread.__init__(self, daemon=True)
        self._db = db
        self._todo_queue = queue.Queue()

    def run(self):
        self._db = self._db.clone()
        while True:
            _LOG.info("CheckWorker check start")
            if self._todo_queue.empty():
                ids = self._db.get_sources_to_fetch()
                for id_ in ids:
                    self._todo_queue.put(id_)

            if not self._todo_queue.empty():
                workers = []
                for _ in range(self._get_num_workers()):
                    worker = FetchWorker(self._db, self._todo_queue)
                    worker.start()
                    workers.append(worker)

                for worker in workers:
                    worker.join()

            _LOG.info("CheckWorker check done")
            time.sleep(60)

        self._db.close()

    def _get_wait_time(self):
        return self._db.get_setting("check_interval", int) or 5

    def _get_num_workers(self):
        return self._db.get_setting("workers", int) or 4


class FetchWorker(threading.Thread):
    def __init__(self, db, todo_queue):
        threading.Thread.__init__(self)
        self._db = db
        self._todo_queue = todo_queue

    def run(self):
        self._db = self._db.clone()
        while not self._todo_queue.empty():
            source_id = self._todo_queue.get()
            self._process_source(source_id)
        self._db.close()

    def _process_source(self, source_id):
        _LOG.info("processing source %d", source_id)
        source = self._db.get_source(id_=source_id, with_state=True)
        try:
            inp = inputs.get_input(source)
            inp.validate()
        except common.ParamError as err:
            _LOG.error("get input for source id=%d error: %s", source_id, err)
            return
        if not inp:
            return

        new_state, entries = inp.load(source.state)

        if new_state.next_update is None:
            last_update = source.state.last_update or datetime.datetime.now()
            new_state.next_update = last_update + \
                datetime.timedelta(
                    minutes=common.parse_interval(source.interval))

        if source.filters:
            entries, new_state = filters.filter_by(source.filters, entries,
                                                   source.state, new_state)

        for entry in entries:
            entry.calculate_oid()

        self._db.insert_entries(entries)
        self._db.save_state(new_state)
        _LOG.info("processing source %d FINISHED, entries=%d, state=%s",
                  source_id, len(entries), str(new_state))
