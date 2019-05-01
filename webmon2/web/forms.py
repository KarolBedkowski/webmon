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

import typing as ty
import logging

from webmon2 import model, inputs, common

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
        self._type = None
        self.fieldname = None
        self.setting_value = False

    @staticmethod
    def from_input_params(param, values=None, prefix='', sett_value=None):
        field = Field()
        field.name = param.name
        field.description = param.description
        if param.options:
            field.type = 'select'
        elif param.type == int:
            field.type = 'number'
        # TODO: bool, float
        else:
            field.type = 'str'
        field.required = param.required and not sett_value
        field.options = [(val, val) for val in param.options or []]
        field.value = values.get(field.name, param.default) \
            if values else None
        field._type = param.type
        field.fieldname = prefix + param.name
        field.setting_value = sett_value
        return field

    def update_from_request(self, form):
        form_value = form.get(self.fieldname)
        if form_value is None:
            return
        if self._type:
            form_value = self._type(form_value)
        self.value = form_value


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
            inputs_names = inputs.enumerate_inputs()
            if self.kind not in inputs_names:
                result["kind"] = "Unknown kind"
        if self.interval:
            try:
                common.parse_interval(self.interval)
            except ValueError:
                result['interval'] = "invalid interval"
        return result

    @staticmethod
    def from_model(source: model.Source, inp_params: list):
        src = SourceForm()
        src.id = source.id
        src.group_id = source.id
        src.kind = source.kind
        src.name = source.name
        src.interval = source.interval or ''
        src.filters = source.filters
        return src

    def update_from_request(self, form):
        group_id = form['group_id'].strip()
        self.group_id = int(group_id) if group_id else None
        self.name = form['name'].strip()
        self.interval = form['interval'].strip()
        for sett in self.settings:
            sett.update_from_request(form)

    def update_model(self, src: model.Source) -> model.Source:
        src = src.clone()
        src.group_id = self.group_id
        src.name = self.name
        src.interval = self.interval
        src.filters = self.filters
        src.settings = {field.name: field.value for field in self.settings}
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


class Filter:
    def __init__(self, name=None):
        self.name = name
        self.parametes = []
