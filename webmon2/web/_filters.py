#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Template filters
"""
import datetime

import markdown2


def _format_body_filter(body):
    if not body:
        return body
#    return publish_parts(
#        body, writer_name='html', settings=None)['fragment']
    return markdown2.markdown(body, extras=["code-friendly"])


def _age_filter(date):
    if date is None:
        return ""
    diff = (datetime.datetime.now() - date).total_seconds()
    if diff < 60:
        return '<1m'
    if diff < 3600:  # < 1h
        return str(int(diff//60)) + "m"
    if diff < 86400:  # < 1d
        return str(int(diff//3600)) + "h"
    return str(int(diff//86400)) + "d"


def register(app):
    app.jinja_env.filters['format_body'] = _format_body_filter
    app.jinja_env.filters['age'] = _age_filter
