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

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if not self.group_id:
            result['group_id'] = "Missing group"
        if not self.name:
            result["name"] = "Missing name"
        if not self.kind:
            result["kind"] = "Missing source kind"
        else:
            from webmon import inputs
            inputs_names = inputs.enumerate_inputs()
            if self.kind not in inputs_names:
                result["kind"] = "Unknown kind"
        if self.interval:
            from webmon import common
            try:
                common.parse_interval(self.interval)
            except ValueError:
                result['interval'] = "invalid interval"
        return result

    @staticmethod
    def from_model(source: model.Source):
        src = SourceForm()
        src.id = source.id
        src.group_id = source.id
        src.kind = source.kind
        src.name = source.name
        src.interval = source.interval or ''
        src.model_settings = source.settings
        src.filters = json.dumps(source.filters) if source.filters else ''
        return src

    def update_from_request(self, form, input_):
        group_id = form['group_id'].strip()
        self.group_id = int(group_id) if group_id else None
        self.name = form['name'].strip()
        self.interval = form['interval'].strip()
        self.filters = form['filters'].strip()
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
        src.interval = self.interval or '1h'
        src.filters = json.loads(self.filters) if self.filters else None
        _LOG.debug("src.filters: %r", src.filters)
        _LOG.debug("self.filters: %r", self.filters)
        src.settings = self.model_settings
        return src


class GroupForm:
    def __init__(self):
        self.id = None
        self.name = None

    @staticmethod
    def from_model(group: model.SourceGroup):
        form = GroupForm()
        form.id = group.id
        form.name = group.name
        return form

    def update_from_request(self, form):
        self.name = form['name'].strip()

    def update_model(self, group: model.SourceGroup):
        group = group.clone()
        group.name = self.name
        return group

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if not self.name:
            result['name'] = "Missing name"
        return result
