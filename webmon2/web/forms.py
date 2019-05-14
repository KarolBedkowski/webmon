#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
GUI forms
"""

import typing as ty
import logging

from webmon2 import model, sources, common

_ = ty
_LOG = logging.getLogger(__name__)


class InvalidValue(RuntimeError):
    pass


class Field:  # pylint: disable=too-many-instance-attributes
    def __init__(self):
        # internal (system) field name
        self.name = None  # type: str
        # field description
        self.description = None  # type: str
        # field type name
        self.type = None  # type: str
        # field value
        self.value = None
        self.required = False  # type: bool
        self.options = None  # type: ty.Optional[ty.Tuple(ty.Any, str)]
        # field value class
        self.type_class = None
        # field name used in form
        self.fieldname = None  # type: str
        # default value
        self.default_value = None
        # error messge
        self.error = None  # type: ty.Optional[str]

    def __str__(self):
        return common.obj2str(self)

    @staticmethod
    def from_input_params(param, values=None, prefix='', sett_value=None):
        field = Field()
        field.name = param.name
        field.description = param.description
        if param.options:
            field.type = 'select'
        elif param.type == int:
            field.type = 'number'
        elif param.type == bool:
            field.type = 'checkbox'
        else:
            field.type = 'str'
        field.required = param.required and not sett_value
        field.options = [(val, val) for val in param.options or []]
        field.value = values.get(field.name, param.default) \
            if values else None
        field.type_class = param.type
        field.fieldname = prefix + param.name
        field.default_value = sett_value
        return field

    @staticmethod
    def from_setting(setting: model.Setting, prefix):
        field = Field()
        field.name = setting.key
        field.description = setting.description
        if setting.value_type == 'int':
            field.type = 'number'
            field.type_class = int
        elif setting.value_type == 'bool':
            field.type = 'checkbox'
            field.type_class = bool
        else:
            field.type = 'str'
            field.type_class = str
        field.value = setting.value
        field.fieldname = prefix + setting.key
        field.default_value = ''
        return field

    def update_from_request(self, form):
        form_value = form.get(self.fieldname)
        if self.type == 'checkbox':
            self.value = bool(form_value)
            return
        if form_value is None:
            return
        if self.type_class:
            form_value = self.type_class(form_value)
        self.value = form_value


class SourceForm:  # pylint: disable=too-many-instance-attributes
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
            if self.kind not in sources.sources_name():
                result["kind"] = "Unknown kind"
        if self.interval:
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
        src.filters = source.filters
        return src

    def update_from_request(self, form):
        group_id = form['group_id'].strip()
        self.group_id = int(group_id) if group_id else None
        self.name = form['name'].strip()
        self.interval = form['interval'].strip()
        for sett in self.settings or []:
            sett.update_from_request(form)

    def update_model(self, src: model.Source) -> model.Source:
        src = src.clone()
        src.group_id = self.group_id
        src.name = self.name
        src.interval = self.interval
        src.filters = self.filters
        src.settings = {field.name: field.value
                        for field in self.settings or []}
        return src


class GroupForm:
    def __init__(self):
        self.id = None
        self.name = None
        self.feed = None
        self.feed_enabled = None

    def __str__(self):
        return common.obj2str(self)

    @staticmethod
    def from_model(group: model.SourceGroup):
        form = GroupForm()
        form.id = group.id
        form.name = group.name
        form.feed = group.feed
        form.feed_enabled = group.feed and group.feed != 'off'
        return form

    def update_from_request(self, form):
        self.name = form['name'].strip()
        self.feed_enabled = form.get('feed_enabled')
        if self.feed_enabled:
            if self.feed == 'off':
                self.feed = None
        else:
            self.feed = 'off'

    def update_model(self, group: model.SourceGroup):
        group = group.clone()
        group.name = self.name
        group.feed = self.feed
        return group

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if not self.name:
            result['name'] = "Missing name"
        return result


class Filter:  # pylint: disable=too-few-public-methods
    def __init__(self, name=None):
        self.name = name
        self.parametes = []


class FieldsForm:
    def __init__(self, fields=None):
        self.fields = fields or []  # type: ty.List[Field]

    def update_from_request(self, request_form) -> bool:
        """ Update fields from request; return True if no errors"""
        no_errors = True
        for field in self.fields:
            try:
                field.update_from_request(request_form)
            except Exception as err:  # pylint: disable=broad-except
                field.error = str(err)
                no_errors = False
        return no_errors

    def values_map(self) -> ty.Dict[str, ty.Any]:
        return {field.name: field.value for field in self.fields}
