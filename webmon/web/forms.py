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
        self._type = None
        self.fieldname = None

    @staticmethod
    def from_input_params(params, values=None, prefix=''):
        if len(params) == 5:
            params = list(params) + ["str"]
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
        field._type = ftype
        field.fieldname = prefix + fname
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
    def from_model(source: model.Source, inp_params: list):
        src = SourceForm()
        src.id = source.id
        src.group_id = source.id
        src.kind = source.kind
        src.name = source.name
        src.interval = source.interval or ''
        src.filters = source.filters
        src.settings = [
            Field.from_input_params(param, source.settings, 'sett-')
            for param in inp_params]
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
