#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Import/export data in opml format.
"""

import itertools
import logging

from defusedxml import ElementTree as etree
from lxml.builder import E  # pylint: disable=no-name-in-module

from webmon2 import database, model, sources

_LOG = logging.getLogger(__name__)


class InvalidFile(RuntimeError):
    pass


def load_opml(content: bytes):
    root = etree.XML(content)
    if root.tag != "opml":
        raise InvalidFile("content is not opml")
    body = root.find("body")
    data = sorted(_load(body), key=lambda x: x[0])
    return itertools.groupby(data, lambda x: x[0])


def load_data(db, content: bytes, user_id: int):
    for group_name, items in load_opml(content):
        group = database.groups.find(db, user_id, group_name)
        if not group:
            group = model.SourceGroup(name=group_name, user_id=user_id)
            group = database.groups.save(db, group)
            _LOG.debug("import opml - new group: %s", group)
        group_id = group.id
        for _, source in items:
            source.group_id = group_id
            source.user_id = user_id
            source = database.sources.save(db, source)
            _LOG.debug("import opml - new source: %s", source)


def dump_data(db, user_id: int):
    groups = database.groups.get_all(db, user_id)
    gnodes = []
    for group in groups:
        items = (
            _dump_source(source)
            for source in database.sources.get_all(db, user_id, group.id)
        )
        items_filtered = list(filter(lambda x: x is not None, items))
        if items_filtered:
            gnodes.append(
                E.outline(*items_filtered, text=group.name, title=group.name)
            )
    root = E.opml(E.head(E.title("subscriptions")), E.body(*gnodes))
    return etree.tostring(root)


def _dump_source(source):
    scls = sources.get_source_class(source.kind)
    if scls:
        try:
            data = scls.to_opml(source)
            if data:
                return E.outline(**data)
        except NotImplementedError:
            pass
    return None


def _load(node, group=None):
    for snode in node.findall("outline"):
        ntype = snode.attrib.get("type")
        if ntype:
            scls = sources.get_source_class(ntype)
            if scls:
                try:
                    source = scls.from_opml(snode.attrib)
                    if source:
                        yield (group, source)
                except NotImplementedError:
                    pass
                except ValueError as err:
                    _LOG.info("import error %s for %s", err, snode.attrib)
            continue
        ntitle = snode.attrib.get("title")
        if ntitle:
            yield from _load(snode, ntitle)
