#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    import prometheus_client as pc
except ImportError:
    pc = None

from . import common


class MetricsSimple(object):
    """"""
    def __init__(self):
        super(MetricsSimple, self).__init__()

    def push(self, inp, status, process_time):
        print(inp, status, process_time)

    def write(self, total_duration=None):
        print('total duration', total_duration)


class MetricsProm(object):
    """"""
    def __init__(self, out_file):
        super(MetricsProm, self).__init__()
        self._out_file = out_file
        self._registry = pc.CollectorRegistry()
        self._process_time = pc.Summary(
            'webmon_processing_time_seconds', 'Processing time for input',
            labelnames=['input'], registry=self._registry)
        self._errors = pc.Gauge(
            'webmon_processing_errors', "Number of inputs loaded with errors",
            registry=self._registry)
        self._succes = pc.Gauge(
            'webmon_processing_success',
            "Number of inputs successfully loaded", registry=self._registry)
        self._by_status = pc.Gauge(
            "webmon_results", "stats by status", labelnames=['status'],
            registry=self._registry)
        self._total_duration = pc.Gauge(
            'webmon_processing_total_time_secounds',
            "Total update time", registry=self._registry)

    def push(self, inp, status, process_time=None):
        if process_time:
            self._process_time.labels(inp).observe(process_time)
        self._by_status.labels(status).inc()
        if status == common.STATUS_ERROR:
            self._errors.inc()
        else:
            self._succes.inc()

    def write(self, total_duration=None):
        if total_duration:
            self._total_duration.set(total_duration)
        pc.write_to_textfile(self._out_file, self._registry)


METRICS = None


def init_metrics(conf):
    global METRICS
    stats = conf.get('stats') or {}
    if pc:
        prometheus_output = stats.get('prometheus_output')
        if prometheus_output:
            METRICS = MetricsProm(prometheus_output)
            return

    METRICS = MetricsSimple()
