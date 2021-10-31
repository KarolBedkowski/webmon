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
