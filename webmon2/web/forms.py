#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
GUI forms

TODO: Python3.10: use slots in dataclass
"""
from __future__ import annotations

import logging
import typing as ty
import zoneinfo
from dataclasses import dataclass

from webmon2 import common, model, sources

_ = ty
_LOG = logging.getLogger(__name__)

Form = ty.Dict[str, str]  # werkzeug.datastructures.ImmutableMultiDict


class InvalidValue(RuntimeError):
    pass


@dataclass()
class Field:  # pylint: disable=too-many-instance-attributes
    # internal (system) field name
    name: str
    # field description
    description: str
    # field type name
    type: str
    # field name used in form
    fieldname: str
    # field value class
    type_class: ty.Any = None
    # field value
    value: ty.Any = None
    required: bool = False
    options: ty.Optional[ty.List[ty.Tuple[ty.Any, ty.Any]]] = None
    # default value
    default_value: ty.Any = None
    # error messge
    error: ty.Optional[str] = None
    # additional setting for field; i.e. multiline
    parameters: ty.Optional[ty.Dict[str, ty.Any]] = None

    def __str__(self) -> str:
        return common.obj2str(self)

    @staticmethod
    def from_input_params(
        param: common.SettingDef,
        values: ty.Optional[ty.Dict[str, ty.Any]] = None,
        prefix: str = "",
        sett_value: ty.Any = None,
    ) -> Field:
        if param.options:
            field_type = "select"
        elif param.type == int:
            field_type = "number"
        elif param.type == bool:
            field_type = "checkbox"
        else:
            field_type = "str"

        field = Field(
            name=param.name,
            description=param.description,
            type=field_type,
            fieldname=prefix + param.name,
            type_class=param.type,
            required=param.required and not sett_value,
            options=[(val, val) for val in param.options or []],
            value=values.get(param.name, param.default) if values else None,
            default_value=sett_value or param.default or "",
        )
        return field

    @staticmethod
    def from_setting(setting: model.Setting, prefix: str) -> Field:
        field_type_class: ty.Any
        options: ty.Optional[ty.List[ty.Tuple[ty.Any, ty.Any]]] = None

        if setting.value_type == "int":
            field_type = "number"
            field_type_class = int
        elif setting.value_type == "bool":
            field_type = "checkbox"
            field_type_class = bool
        elif setting.value_type == "tz":
            field_type = "select"
            field_type_class = str
            options = sorted((i, i) for i in zoneinfo.available_timezones())
        else:
            field_type = "str"
            field_type_class = str

        field = Field(
            name=setting.key,
            description=setting.description,
            value=setting.value,
            fieldname=prefix + setting.key,
            default_value="",
            type=field_type,
            type_class=field_type_class,
            options=options,
        )
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

    def get_parameter(self, key: str, default: ty.Any = None) -> ty.Any:
        if self.parameters:
            return self.parameters.get(key, default)

        return default


@dataclass
class SourceForm:  # pylint: disable=too-many-instance-attributes
    id: ty.Optional[int]
    group_id: int
    kind: str
    name: str
    interval: str
    status: int
    mail_report: int
    default_score: int
    settings: ty.Optional[ty.List[Field]] = None
    filters: ty.Optional[ty.List[ty.Dict[str, ty.Any]]] = None

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
        form = SourceForm(
            id=source.id,
            group_id=source.group_id,
            kind=source.kind,
            name=source.name or "",
            interval=source.interval or "",
            filters=source.filters,
            status=source.status.value,
            mail_report=source.mail_report.value,
            default_score=source.default_score or 0,
        )
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
        src.filters = self.filters  # type: ignore
        src.settings = {
            field.name: field.value for field in self.settings or []
        }
        src.status = model.SourceStatus(self.status)
        src.mail_report = model.MailReportMode(self.mail_report)
        src.default_score = self.default_score
        return src


@dataclass
class GroupForm:
    id: ty.Optional[int] = None
    name: ty.Optional[str] = None
    feed: ty.Optional[str] = None
    feed_enabled: bool = True
    mail_report: int = 1

    def __str__(self) -> str:
        return common.obj2str(self)

    @staticmethod
    def from_model(group: model.SourceGroup) -> GroupForm:
        form = GroupForm(
            id=group.id,
            name=group.name,
            feed=group.feed,
            feed_enabled=bool(group.feed) and group.feed != "off",
            mail_report=group.mail_report.value,
        )
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
        group.name = self.name  # type: ignore
        group.feed = self.feed
        group.mail_report = model.MailReportMode(self.mail_report)
        return group

    def validate(self) -> ty.Dict[str, str]:
        result = {}
        if not self.name:
            result["name"] = "Missing name"

        return result


class Filter:  # pylint: disable=too-few-public-methods
    __slots__ = ("name", "parameters")

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.parameters: ty.List[ty.Any] = []


class FieldsForm:
    __slots__ = ("fields",)

    def __init__(self, fields: ty.Optional[ty.List[Field]] = None) -> None:
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
@dataclass
class UserForm:
    id: ty.Optional[int]
    login: str
    active: bool
    admin: bool
    email: str
    password1: ty.Optional[str] = None
    password2: ty.Optional[str] = None
    has_totp: bool = False
    disable_totp: bool = False

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
        form = UserForm(
            id=user.id,
            login=user.login or "",
            email=user.email or "",
            active=user.active,
            admin=user.admin,
            has_totp=bool(user.totp),
        )
        return form

    def update_from_request(self, form: Form) -> None:
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
