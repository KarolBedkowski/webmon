#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Common gui api functions
"""
import typing as ty

from webmon2 import model

PAGE_LIMIT = 25


def preprate_entries_list(entries: ty.List[model.Entry], page: int,
                          total_entries: int) -> ty.Dict[str, ty.Any]:
    info = {
        'min_id': min(entry.id for entry in entries) if entries else None,
        'max_id': max(entry.id for entry in entries) if entries else None,
        'more': page is not None and (page + 1) * PAGE_LIMIT < total_entries,
        'entries': entries,
        'next_page': (min(page + 1, int(total_entries / PAGE_LIMIT))
                      if page is not None else None),
        'prev_page': (max(0, page - 1) if page is not None else None),
        'total_entries': total_entries,
        'page': page,
    }
    return info
