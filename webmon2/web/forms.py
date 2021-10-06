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
from __future__ import annotations

import logging
import typing as ty

from webmon2 import common, model, sources

_ = ty
_LOG = logging.getLogger(__name__)

Form = ty.Dict[str, str]  # werkzeug.datastructures.ImmutableMultiDict


class InvalidValue(RuntimeError):
    pass


class Field:  # pylint: disable=too-many-instance-attributes
    def __init__(self):
        # internal (system) field name
        self.name: str = None
        # field description
        self.description: str = None
        # field type name
        self.type: str = None
        # field value
        self.value = None
        self.required: bool = False
        self.options: ty.Optional[ty.List[ty.Tuple[ty.Any, ty.Any]]] = None
        # field value class
        self.type_class = None
        # field name used in form
        self.fieldname: str = None
        # default value
        self.default_value = None
        # error messge
        self.error: ty.Optional[str] = None

        # additional setting for field; i.e. multiline
        self.parameters: ty.Optional[ty.Dict[str, ty.Any]] = None

    def __str__(self):
        return common.obj2str(self)

    @staticmethod
    def from_input_params(
        param: common.SettingDef,
        values: ty.Optional[ty.Dict[str, ty.Any]] = None,
        prefix: str = "",
        sett_value=None,
    ) -> Field:
        field = Field()
        field.name = param.name
        field.description = param.description
        if param.options:
            field.type = "select"
        elif param.type == int:
            field.type = "number"
        elif param.type == bool:
            field.type = "checkbox"
        else:
            field.type = "str"

        field.required = param.required and not sett_value
        field.options = [(val, val) for val in param.options or []]
        field.value = values.get(field.name, param.default) if values else None
        field.type_class = param.type
        field.fieldname = prefix + param.name
        field.default_value = sett_value or param.default or ""
        return field

    @staticmethod
    def from_setting(setting: model.Setting, prefix: str) -> Field:
        field = Field()
        field.name = setting.key
        field.description = setting.description
        if setting.value_type == "int":
            field.type = "number"
            field.type_class = int
        elif setting.value_type == "bool":
            field.type = "checkbox"
            field.type_class = bool
        else:
            field.type = "str"
            field.type_class = str

        field.value = setting.value
        field.fieldname = prefix + setting.key
        field.default_value = ""
        return field

    def update_from_request(self, form: Form) -> None:
        form_value = form.get(self.fieldname)
        if self.type == "checkbox":
            self.value = bool(form_value)
            return

        if form_value is None:
            if self.required:
                raise ValueError("missing value")
            return

        if self.type == "number":
            if form_value == "":
                self.value = None
                return

        if self.type_class:
            form_value = self.type_class(form_value)

        self.value = form_value

    def get_parameter(self, key: str, default=None):
        if self.parameters:
            return self.parameters.get(key, default)

        return default


class SourceForm:  # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.id: int = None
        self.group_id: int = None
        self.kind: str = None
        self.name: str = None
        self.interval: str = None
        self.settings: ty.List[str, ty.Any] = None
        self.filters: ty.List[ty.Dict[str, ty.Any]] = None
        self.status: int = None
        self.mail_report: int = None
        self.default_score: int = 0

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if not self.group_id:
            result["group_id"] = "Missing group"

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
                result["interval"] = "invalid interval"

        return result

    @staticmethod
    def from_model(source: model.Source) -> SourceForm:
        form = SourceForm()
        form.id = source.id
        form.group_id = source.group_id
        form.kind = source.kind
        form.name = source.name
        form.interval = source.interval or ""
        form.filters = source.filters
        form.status = source.status.value
        form.mail_report = source.mail_report.value
        form.default_score = source.default_score or 0
        return form

    def update_from_request(self, form: Form) -> None:
        group_id = form["group_id"].strip()
        self.group_id = int(group_id)
        self.name = form["name"].strip()
        self.interval = form["interval"].strip()
        self.status = int(form.get("status", 0))
        self.mail_report = int(form.get("mail_report", "0"))
        self.default_score = int(form.get("default_score", "0"))
        for sett in self.settings or []:
            sett.update_from_request(form)

    def update_model(self, src: model.Source) -> model.Source:
        src = src.clone()
        src.group_id = self.group_id
        src.name = self.name
        src.interval = self.interval
        src.filters = self.filters
        src.settings = {
            field.name: field.value for field in self.settings or []
        }
        src.status = model.SourceStatus(self.status)
        src.mail_report = model.MailReportMode(self.mail_report)
        src.default_score = self.default_score
        return src


class GroupForm:
    def __init__(self):
        self.id: int = None
        self.name: str = None
        self.feed: ty.Optional[str] = None
        self.feed_enabled: bool = None
        self.mail_report: int = None

    def __str__(self):
        return common.obj2str(self)

    @staticmethod
    def from_model(group: model.SourceGroup) -> GroupForm:
        form = GroupForm()
        form.id = group.id
        form.name = group.name
        form.feed = group.feed
        form.feed_enabled = bool(group.feed) and group.feed != "off"
        form.mail_report = group.mail_report.value
        return form

    def update_from_request(self, form: Form) -> None:
        self.name = form["name"].strip()
        self.feed_enabled = bool(form.get("feed_enabled", None))
        if self.feed_enabled:
            if self.feed == "off":
                self.feed = None
        else:
            self.feed = "off"

        self.mail_report = int(form.get("mail_report", 1))

    def update_model(self, group: model.SourceGroup) -> model.SourceGroup:
        group = group.clone()
        group.name = self.name
        group.feed = self.feed
        group.mail_report = model.MailReportMode(self.mail_report)
        return group

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if not self.name:
            result["name"] = "Missing name"

        return result


class Filter:  # pylint: disable=too-few-public-methods
    def __init__(self, name=None):
        self.name: str = name
        self.parameters = []


class FieldsForm:
    def __init__(self, fields: ty.Optional[ty.List[Field]] = None):
        self.fields: ty.List[Field] = fields or []

    def update_from_request(self, request_form: Form) -> bool:
        """Update fields from request; return True if no errors"""
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


# pylint: disable=too-many-instance-attributes
class UserForm:
    def __init__(self):
        self.id: int = None
        self.login: str = None
        self.active: bool = None
        self.email: str = None
        self.admin: bool = None
        self.password1: str = None
        self.password2: str = None
        self.disable_totp: bool = None
        self.has_totp: bool = None

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if self.password1 and self.password1 != self.password2:
            result["password1"] = "Passwords not match"

        if not self.login:
            result["login"] = "Missing login"

        if not self.id and not self.password1:
            result["password1"] = "Password is required for new user"

        return result

    @staticmethod
    def from_model(user: model.User) -> UserForm:
        form = UserForm()
        form.id = user.id
        form.login = user.login or ""
        form.email = user.email or ""
        form.active = user.active
        form.admin = user.admin
        form.has_totp = bool(user.totp)
        return form

    def update_from_request(self, form: Form):
        self.login = form["login"].strip()
        self.email = form["email"].strip()
        self.active = bool(form.get("active"))
        self.admin = bool(form.get("admin"))
        self.password1 = form["password1"]
        self.password2 = form["password2"]
        self.disable_totp = bool(form.get("disable_totp"))

    def update_model(self, user: model.User) -> model.User:
        user = user.clone()
        if not user.login:
            user.login = self.login

        user.email = self.email
        user.active = self.active
        user.admin = self.admin
        if self.disable_totp:
            user.totp = None

        return user
