#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
GUI forms
"""

import json
import typing as ty
import logging

from webmon import model

_ = ty
_LOG = logging.getLogger(__name__)


class Field:
    def __init__(self):
        self.name = None  # type: str
        self.description = None  # type: str
        self.type = None  # type: str
        self.value = None
        self.required = False  # type: bool
        self.options = None  # type: ty.Optional[ty.Tuple(ty.Any, str)]

    @staticmethod
    def from_input_params(params, values=None):
        fname, fdescr, fdefault, frequired, foptions, ftype = params
        field = Field()
        field.name = fname
        field.description = fdescr
        if foptions:
            field.type = 'select'
        elif ftype == int:
            field.type = 'number'
        else:
            field.type = 'str'
        field.required = frequired
        field.options = [(val, val) for val in foptions or []]
        field.value = values.get(field.name, fdefault) if values else None
        return field


class SourceForm:
    def __init__(self):
        self.id = None
        self.group_id = None
        self.kind = None
        self.name = None
        self.interval = None
        self.model_settings = None
        self.settings = None
        self.filters = None

    @staticmethod
    def from_model(source: model.Source):
        src = SourceForm()
        src.id = source.id
        src.group_id = source.id
        src.kind = source.kind
        src.name = source.name
        src.interval = source.interval
        src.model_settings = source.settings
        src.filters = json.dumps(source.filters) if source.filters else ''
        return src

    def update_from_request(self, form, input_):
        group_id = form['group_id']
        self.group_id = int(group_id) if group_id else None
        self.name = form['name']
        self.interval = int(form['interval'])
        self.filters = form['filters']
        self.model_settings = self.model_settings or {}
        param_types = input_.get_param_types()
        for key, val in form.items():
            if key.startswith('sett-'):
                param_name = key[5:]
                if val:
                    param_type = param_types[param_name]
                    self.model_settings[param_name] = param_type(val)
                else:
                    self.model_settings[param_name] = None

    def update_model(self, src: model.Source) -> model.Source:
        src = src.clone()
        src.group_id = self.group_id
        src.name = self.name
        src.interval = self.interval
        src.filters = json.loads(self.filters) if self.filters else None
        _LOG.debug("src.filters: %r", src.filters)
        _LOG.debug("self.filters: %r", self.filters)
        src.settings = self.model_settings
        return src
