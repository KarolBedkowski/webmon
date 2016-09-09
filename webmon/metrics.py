#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

try:
    import prometheus_client as pc
except ImportError:
    pc = None

from . import common


class MetricsSimple(object):
    """Simple metric logger"""
    def __init__(self):
        super(MetricsSimple, self).__init__()
        self.log = logging.getLogger(self.__class__.__name__)

    def put(self, inp, status, process_time):
        self.log.debug("metric %s status=%s, processing time=%s",
                       inp, status, process_time)

    def write(self, total_duration=None):
        self.log.debug("total duration=%s", total_duration)

    def put_output_source_files(self, inputs: int, all_items: int):
        self.log.debug("output: inputs=%d; all_files=%d", inputs, all_items)

    def put_output(self, output: str, process_time: float, ok: bool):
        self.log.debug("output %s processing time=%s, status=%s",
                       output, process_time, ok)


class MetricsProm(MetricsSimple):
    """Export metrics to prometheus"""
    def __init__(self, out_file):
        super(MetricsProm, self).__init__()
        self._out_file = out_file
        self._process_time = pc.Summary(
            'webmon_processing_time_seconds',
            'Processing time for input',
            ['input'])
        self._errors = pc.Gauge(
            'webmon_processing_errors',
            "Number of inputs loaded with errors", [])
        self._succes = pc.Gauge(
            'webmon_processing_success',
            "Number of inputs successfully loaded", [])
        self._by_status = pc.Gauge(
            "webmon_results", "stats by status", ['status'])
        self._total_duration = pc.Gauge(
            'webmon_processing_total_time_secounds',
            "Total update time", [])
        self._outp_src_inp = pc.Gauge(
            'webmon_output_source_inputs',
            "Number of inputs processed in report", [])
        self._outp_src_files = pc.Gauge(
            'webmon_output_source_files',
            "Number of files processed in report", [])
        self._outp_process_time = pc.Summary(
            'webmon_output_time_seconds',
            'Generate report time for output',
            ['output'])
        self._outp_status = pc.Gauge(
            'webmon_output_status',
            "Status processed in report", ["output"])
        pc.REGISTRY.register(pc.PROCESS_COLLECTOR)

    def put(self, inp, status, process_time=None):
        if process_time:
            self._process_time.labels(inp).observe(process_time)
        self._by_status.labels(status).inc()
        if status == common.STATUS_ERROR:
            self._errors.inc()
        else:
            self._succes.inc()

    def put_output_source_files(self, inputs: int, all_items: int):
        self._outp_src_inp.set(inputs)
        self._outp_src_files.set(all_items)

    def put_output(self, output: str, process_time: float, ok: bool):
        self._outp_process_time.labels(output).observe(process_time)
        self._outp_status.labels(output).set(1 if ok else -1)

    def write(self, total_duration=None):
        if total_duration:
            self._total_duration.set(total_duration)
        pc.write_to_textfile(self._out_file, pc.REGISTRY)


_METRICS = None


def init_metrics(conf):
    global _METRICS
    stats = conf.get('stats') or {}
    if pc:
        prometheus_output = stats.get('prometheus_output')
        if prometheus_output:
            _METRICS = MetricsProm(prometheus_output)
            return

    _METRICS = MetricsSimple()


def put_metric(ctx: common.Context, result: common.Result=None,
               status: str=None):
    name = ctx.name
    status = status or (result.meta['status'] if result else None)
    process_time = result.meta['update_duration'] if result else None
    _METRICS.put(name, status, process_time)


def write_metrics(total_duration: float):
    _METRICS.write(total_duration)


def put_metrics_output_sources(inputs: int, all_items: int):
    _METRICS.put_output_source_files(inputs, all_items)


def put_metrics_output(output: str, process_time: float, ok: bool):
    _METRICS.put_output(output, process_time, ok)
