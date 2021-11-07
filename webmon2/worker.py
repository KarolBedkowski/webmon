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
from __future__ import annotations

import datetime
import gc
import logging
import queue
import random
import re
import threading
import time
import typing as ty
from configparser import ConfigParser

from prometheus_client import Counter, Gauge

from . import common, database, filters, formatters, mailer, model, sources

_LOG = logging.getLogger(__name__)
_SOURCES_PROCESSED = Counter(
    "webmon2_sources_processed", "Sources processed count"
)
_SOURCES_PROCESSED_ERRORS = Counter(
    "webmon2_sources_processed_errors", "Sources processed with errors count"
)
_WORKER_PROCESSING_TIME = Gauge(
    "webmon2_worker_processing_seconds",
    "Worker processing time",
)
_SOURCE_PROCESSING_TIME = Gauge(
    "webmon2_source_processing_seconds",
    "Source processing time",
    ["source_id"],
)
_CLEAN_COUNTER = Counter(
    "webmon2_clean_items",
    "Number of deleted entries",
    ["user_id", "area"],
)
_CLEANUP_INTERVAL = 60 * 60 * 24


class CheckWorker(threading.Thread):
    def __init__(
        self, conf: ConfigParser, debug: bool = False, sdn: ty.Any = None
    ) -> None:
        threading.Thread.__init__(self, daemon=True)
        # sources id to process
        self._todo_queue: queue.Queue[int] = queue.Queue()
        # application configuration
        self._conf: ConfigParser = conf
        # number of maximal workers to launch
        self.num_workers: int = conf.getint("main", "workers")
        # launch in debug
        self._debug: bool = debug
        # systemd object
        self._sdn = sdn
        # time of next cleanup start
        self._next_cleanup_start: float = time.time()

    def _notify(self, msg: str) -> None:
        """
        Notify systemd (if available) sending `msg`.
        """
        if self._sdn:
            self._sdn.notify(msg)

    def run(self) -> None:
        _LOG.info("CheckWorker started; workers: %d", self.num_workers)
        gc_cntr = 0
        while True:
            time.sleep(15 if self._debug else 60)
            self._notify("STATUS=processing")
            start = time.time()
            with database.DB.get() as db:
                try:
                    now = time.time()
                    if now > self._next_cleanup_start:
                        _delete_old_entries(db)
                        self._next_cleanup_start = now + _CLEANUP_INTERVAL

                    _LOG.debug("CheckWorker check start")
                    ids = database.sources.get_sources_to_fetch(db)
                    for id_ in ids:
                        self._todo_queue.put(id_)

                    if not self._todo_queue.empty():
                        # some work to do; launch workers
                        workers = [
                            self._start_worker(idx)
                            for idx in range(min(self.num_workers, len(ids)))
                        ]
                        # wait for work completed
                        for worker in workers:
                            worker.join()

                    _LOG.debug("CheckWorker check done")
                    self._notify("STATUS=mailing")
                    _send_mails(db, self._conf)
                except Exception as err:  # pylint: disable=broad-except
                    _LOG.exception("CheckWorker thread error: %s", err)

            _WORKER_PROCESSING_TIME.set(time.time() - start)

            gc_cntr += 1
            if gc_cntr == 30:
                gc.collect()
                gc_cntr = 0

            self._notify("STATUS=running")

    def _start_worker(self, idx: int) -> FetchWorker:
        worker = FetchWorker(str(idx), self._todo_queue, self._conf)
        worker.start()
        _LOG.debug("CheckWorker worker %s started", idx)
        return worker


class FetchWorker(threading.Thread):
    def __init__(
        self, idx: str, todo_queue: queue.Queue[int], conf: ConfigParser
    ) -> None:
        threading.Thread.__init__(self)
        # id of thread
        self._idx: str = idx + ":" + str(id(self))
        # queue of sources id to process
        self._todo_queue: queue.Queue[int] = todo_queue
        # app configuration
        self._conf: ConfigParser = conf

    def run(self) -> None:
        while not self._todo_queue.empty():
            source_id = self._todo_queue.get()
            start = time.time()
            with database.DB.get() as db:
                source = None
                try:
                    db.begin()
                    # load source from database
                    source = database.sources.get(
                        db, id_=source_id, with_state=True
                    )
                    self._process_source(db, source)
                except Exception as err:  # pylint: disable=broad-except
                    _LOG.exception(
                        "[%s] process source %d error", self._idx, source_id
                    )
                    db.rollback()
                    if source:
                        _save_state_error(db, source, str(err))
                finally:
                    db.commit()
            _SOURCE_PROCESSING_TIME.labels(source_id).set(time.time() - start)

    def _process_source(self, db: database.DB, source: model.Source) -> None:
        """
        Process one source.

        Raises:
            any exception - according to precessed source type.
        """
        _SOURCES_PROCESSED.inc()
        _LOG.debug("[%s] processing source %d", self._idx, source.id)
        start = time.time()

        sys_settings = database.settings.get_dict(db, source.user_id)

        # get source object; errors are propagated upwards
        try:
            src = self._get_src(source, sys_settings)
        except sources.UnknownInputException as err:
            raise Exception(f"unsupported input {source.kind}") from err

        assert source.state and src
        # load data
        new_state, entries = src.load(source.state)
        if new_state.status == model.SourceStateStatus.ERROR:
            # stop processing source when error occurred
            _save_state_error(
                db, source, new_state.error or "error", new_state
            )
            _LOG.info(
                "[%s] process source %d error: %s",
                self._idx,
                source.id,
                new_state.error,
            )
            return

        assert source.state and source.interval is not None
        # calculate next update time; source may overwrite user settings
        if new_state.last_update:
            last_update = max(new_state.last_update, datetime.datetime.now())
        else:
            new_state.last_update = last_update = datetime.datetime.now()

        next_update = last_update + datetime.timedelta(
            seconds=common.parse_interval(source.interval)
        )
        if (
            new_state.next_update is None
            or new_state.next_update < next_update
        ):
            new_state.next_update = next_update

        # filter entries
        if source.filters:
            entries = filters.filter_by(
                source.filters, entries, source.state, new_state, db
            )

        # process entriec, calcuate oids, sanitize content
        entries = self._final_filter_entries(entries)
        # calculate scoring & update entries state
        entries = self._score_entries(
            entries, db, source.user_id, sys_settings
        )
        entries = list(entries)
        if entries:
            # save entries
            max_date = max(entry.updated for entry in entries if entry.updated)
            new_state.set_prop("last_entry_date", str(max_date))
            database.entries.save_many(db, entries)
            database.groups.update_state(db, source.group_id, max_date)
            icon = entries[0].icon
            if not new_state.icon and icon:
                new_state.icon = icon

        # update source state properties
        new_state.set_prop("last_check", str(datetime.datetime.now()))
        new_state.set_prop(
            "last_update_duration", f"{time.time() - start:0.2f}"
        )
        database.sources.save_state(db, new_state, source.user_id)
        # if source was updated - save new version
        updated_source = src.updated_source
        if updated_source:
            _LOG.debug("[%s] source %d updated", self._idx, source.id)
            database.sources.save(db, updated_source)

        _LOG.debug(
            "[%s] processing source %d FINISHED, entries=%d, state=%s",
            self._idx,
            source.id,
            len(entries),
            str(new_state),
        )

    def _final_filter_entries(self, entries: model.Entries) -> model.Entries:
        """
        Process entries:
            1. calculate oid and remove duplicates
            2. validate entries
            3. calculate icon hashes
            4. sanitize content
        """
        entries_oids = set()
        for entry in entries:
            entry.calculate_oid()
            if entry.oid in entries_oids:
                _LOG.debug("[%s] doubled entry %s", self._idx, entry)
                continue

            entry.validate()
            entry.calculate_icon_hash()
            if entry.content:
                if not entry.content_type:
                    _LOG.warning(
                        "[%s] no content type for entry: %r", self._idx, entry
                    )
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
        self,
        entries: model.Entries,
        db: database.DB,
        user_id: int,
        sys_settings: ty.Dict[str, str],
    ) -> model.Entries:
        """
        Apply scoring for `entries`. If entry score is below `minimal_score`
        user settings - mark it as read.
        """
        # load scoring
        scss = list(self._load_scoring(db, user_id))
        if not scss:
            # no rules
            yield from entries
            return

        min_score = int(sys_settings.get("minimal_score", "-20"))

        for entry in entries:
            entry.score += sum(
                score_change
                for pattern, score_change in scss
                if (entry.title and pattern.match(entry.title))
                or (entry.content and pattern.match(entry.content))
            )
            if entry.score < min_score:
                entry.read_mark = model.EntryReadMark.READ

            yield entry

    def _load_scoring(
        self, db: database.DB, user_id: int
    ) -> ty.Iterator[ty.Tuple[re.Pattern[str], int]]:
        #    ) -> ty.Iterator[ty.Tuple[re.Pattern[str], int]]:  # py3.7
        """
        Load scoring rules and compile list of (re pattern, score) rules
        """
        for scs in database.scoring.get_active(db, user_id):
            _LOG.debug("[%s] scs: %s", self._idx, scs)
            try:
                cre = re.compile(
                    ".*(" + scs.pattern + ").*",
                    re.IGNORECASE | re.MULTILINE | re.DOTALL,
                )
                yield (cre, scs.score_change)
            except re.error as err:
                _LOG.warning("compile scoring pattern error: %s %s", scs, err)

    def _get_src(
        self, source: model.Source, sys_settings: ty.Dict[str, str]
    ) -> ty.Optional[sources.AbstractSource]:
        """
        Create and initialize source object according to `source` configuration.
        """
        if not source.interval:
            interval = sys_settings.get("interval") or "1d"
            _LOG.debug(
                "[%s] source %d has no interval; using default: %r",
                self._idx,
                source.id,
                interval,
            )
            source.interval = interval or "1d"

        src = sources.get_source(source, sys_settings)
        src.validate()
        return src


def _delete_old_entries(db: database.DB) -> None:
    """
    Remove old data from database.
    For each user:
        1. find and delete old entries
        2. remove unused binaries
        3. remove old source states
    """
    users = list(database.users.get_all(db))
    for user in users:
        assert user.id
        try:
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
            _CLEAN_COUNTER.labels(user.id, "entries").inc(deleted_entries)
            _CLEAN_COUNTER.labels(user.id, "oids").inc(deleted_oids)

            removed_bin = database.binaries.remove_unused(db, user.id)
            _LOG.info("removed %d binaries for user %d", removed_bin, user.id)
            _CLEAN_COUNTER.labels(user.id, "binaries").inc(removed_bin)
            db.commit()
        except Exception as err:  # pylint: disable=broad-except
            db.rollback()
            _LOG.warning("_delete_old_entries error: %s", err)

    db.begin()
    try:
        states, entries = database.binaries.clean_sources_entries(db)
        _LOG.info("cleaned %d source states and %d entries", states, entries)
        _CLEAN_COUNTER.labels("", "bin_states").inc(states)
        _CLEAN_COUNTER.labels("", "bin_entries").inc(entries)
        db.commit()
    except Exception as err:  # pylint: disable=broad-except
        db.rollback()
        _LOG.warning("_delete_old_entries error: %s", err)


def _send_mails(db: database.DB, conf: ConfigParser) -> None:
    """
    For each user search and send reports by mail.

    """
    if not conf.getboolean("smtp", "enabled", fallback=False):
        _LOG.debug("_send_mails disabled")
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


def _calc_next_check_on_error(source: model.Source) -> datetime.datetime:
    """
    Calculate next update time for `source` for error result as now +
    source.interval (or 1 day) + random time between 1 and 3 hours.
    """
    next_check_delta = common.parse_interval(source.interval or "1d")
    # add some random time
    next_check_delta += random.randint(3600, 3 * 3600)
    return datetime.datetime.now() + datetime.timedelta(
        seconds=next_check_delta
    )


def _save_state_error(
    db: database.DB,
    source: model.Source,
    err: str,
    state: ty.Optional[model.SourceState] = None,
) -> None:
    """
    Create and save `SourceState` with state = `ERROR` for `source` and `err`
    message.
    """
    _SOURCES_PROCESSED_ERRORS.inc()
    assert source.state

    new_state = state if state else source.state.new_error(str(err))
    new_state.next_update = _calc_next_check_on_error(source)
    new_state.set_prop("last_check", str(datetime.datetime.now()))

    database.sources.save_state(db, new_state, source.user_id)
