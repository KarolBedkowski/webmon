#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Common functions for db access
"""
import typing as ty

from psycopg2 import extensions

Cursor = ty.Type[extensions.cursor]


class NotFound(Exception):
    pass


class Query:
    def __init__(self, cols: str, from_: str) -> None:
        self.cols: ty.List[str] = [cols]
        self.from_: ty.List[str] = [from_]
        self.where: ty.List[str] = []
        self.order: ty.Optional[str] = None
        self.limit: bool = False
        self.offset: bool = False

    def add_select(self, col: str) -> None:
        self.cols.append(col)

    def add_from(self, from_: str) -> None:
        self.from_.append(from_)

    def add_where(self, where: str) -> None:
        self.where.append(where)

    def build(self) -> str:
        return "\n".join(self._collect())

    def _collect(self) -> ty.Iterator[str]:
        yield "SELECT"
        yield ", ".join(self.cols)
        yield "FROM"
        yield "\n".join(self.from_)
        if self.where:
            yield "WHERE"
            yield from self.where

        if self.order:
            yield f"ORDER BY {self.order}"

        if self.limit:
            yield "LIMIT %(limit)s"

        if self.offset:
            yield "OFFSET %(offset)s"
