#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Application metrics.

Copyright (c) Karol Będkowski, 2016-2017

This file is part of webmon.
Licence: GPLv2+
"""

import logging
import threading
import typing as ty

try:
    import prometheus_client as pc
except ImportError:
    pc = None

from . import common

__author__ = "Karol Będkowski"
__copyright__ = "Copyright (c) Karol Będkowski, 2016-2017"


class AbstractMetricCollector(object):
    """Collector for metrics and stats"""
    def __init__(self, conf):
        super().__init__()
        self.conf = conf

    def write(self):
        pass

    def put_input(self, ctx: common.Context, result: common.Result=None,
                  status: str=None):
        pass

    def put_loading_summary(self, total_duration: float=None):
        pass

    def put_output(self, output: str, process_time: float, status: str):
        pass

    def put_output_summary(self, inputs: int, files: int,
                           total_duration: float):
        pass

    def put_total(self, total_duration: float=None):
        pass


class MetricsSimple(AbstractMetricCollector):
    """Simple metric logger"""
    def __init__(self, conf):
        super().__init__(conf)
        self._stats = []
        self._lock = threading.Lock()

    def write(self):
        log = logging.getLogger(self.__class__.__name__)
        with self._lock:
            for stat in self._stats:
                log.debug(stat)

    def put_input(self, ctx: common.Context, result: common.Result=None,
                  status: ty.Union[str, property]=None):
        status = status or (result.status if result else None)
        process_time = result.meta['update_duration'] if result else None
        with self._lock:
            self._stats.append(
                "metric {} status={}, processing time={}".format(
                    ctx.name, status, process_time))

    def put_loading_summary(self, total_duration: float=None):
        with self._lock:
            self._stats.append(
                'loading.total_duration: {}'.format(total_duration))

    def put_output(self, output: str, process_time: float, status: str):
        with self._lock:
            self._stats.append(
                "output {} processing time={}, status={}".format(
                    output, process_time, status))

    def put_output_summary(self, inputs: int, files: int,
                           total_duration: float):
        with self._lock:
            self._stats.append("output.summary inputs={}; all_files={}".format(
                inputs, files))

    def put_total(self, total_duration: float=None):
        with self._lock:
            self._stats.append("total duration={}".format(total_duration))


class MetricsProm(AbstractMetricCollector):
    """Export metrics to prometheus"""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, conf):
        super().__init__(conf)
        # inputs
        self._inp_loading_time = pc.Gauge(
            'webmon_input_time_seconds',
            'Loading time for input',
            ['input'])
        self._inp_by_status = pc.Gauge(
            "webmon_input_processing_results",
            "stats by status", ['status', 'input'])

        # global times
        self._total_processing_time = pc.Gauge(
            'webmon_processing_total_time_seconds',
            'Processing total time', [])
        self._total_loading_duration = pc.Gauge(
            'webmon_loading_total_time_secounds',
            "Total update time", [])
        self._total_output_time = pc.Gauge(
            'webmon_output_total_time_seconds',
            'Generate all reports time.', [])

        # outputs global
        self._outp_src_inp = pc.Gauge(
            'webmon_output_source_inputs',
            "Number of inputs processed in report", [])
        self._outp_src_files = pc.Gauge(
            'webmon_output_source_files',
            "Number of files processed in report", [])

        # output
        self._outp_process_time = pc.Gauge(
            'webmon_output_generate_time_seconds',
            'Generate report time for output',
            ['output'])
        self._outp_status = pc.Gauge(
            'webmon_output_results',
            "Status processed in report by status",
            ['status', "output"])

    def write(self):
        filename = common.prepare_filename(self.conf['prometheus_output'])
        pc.write_to_textfile(filename, pc.REGISTRY)

    def put_input(self, ctx: common.Context, result: common.Result=None,
                  status: ty.Union[str, property]=None):
        status = status or (result.status if result else None)
        process_time = result.meta['update_duration'] if result else None
        if process_time:
            # pylint: disable=no-member
            self._inp_loading_time.labels(ctx.name).set(process_time)
        # pylint: disable=no-member
        self._inp_by_status.labels(status, ctx.name).inc()

    def put_loading_summary(self, total_duration: float=None):
        self._total_loading_duration.set(total_duration)

    def put_output(self, output: str, process_time: float, status: str):
        # pylint: disable=no-member
        self._outp_process_time.labels(output).set(process_time)
        # pylint: disable=no-member
        self._outp_status.labels(status, output).inc()

    def put_output_summary(self, inputs: int, files: int,
                           total_duration: float):
        self._outp_src_inp.set(inputs)
        self._outp_src_files.set(files)
        self._total_output_time.set(total_duration)

    def put_total(self, total_duration: float=None):
        self._total_processing_time.set(total_duration)


COLLECTOR = MetricsSimple(None)


def configure(conf):
    global COLLECTOR

    stats = conf.get('stats') or {}
    if pc:
        prometheus_output = stats.get('prometheus_output')
        if prometheus_output:
            COLLECTOR = MetricsProm(stats)
