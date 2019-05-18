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

from lxml import etree
from lxml.builder import E

from webmon2 import model, database, sources


_LOG = logging.getLogger(__name__)


class InvalidFile(RuntimeError):
    pass


def load_opml(filename):
    root = etree.parse(filename).getroot()
    if root.tag != 'opml':
        raise InvalidFile('file is not opml')
    body = root.find('body')
    data = sorted(_load(body))
    return itertools.groupby(data, lambda x: x[0])


def load_data(filename: str, user_id: int):
    with database.DB.get() as db:
        for group_name, items in load_opml(filename):
            group = database.groups.find(db, user_id, group_name)
            if not group:
                group = model.SourceGroup(name=group_name, user_id=user_id)
                group = database.groups.save(db, group)
            group_id = group.id
            for item_title, item_url in items:
                source = model.Source()
                source.kind = 'rss'
                source.name = item_title
                source.group_id = group_id
                source.settings = {'url': item_url}
                source.user_id = user_id
                source = database.sources.save(db, source)


def dump_data(db, user_id: int):
    groups = database.groups.get_all(db, user_id)
    gnodes = []
    for group in groups:
        items = (_dump_source(source)
                 for source
                 in database.sources.get_all(db, user_id, group.id))
        items = list(filter(lambda x: x is not None, items))
        if items:
            gnodes.append(E.outline(*items, text=group.name, title=group.name))
    root = E.opml(
        E.head(
            E.title("subscriptions")
        ),
        E.body(*gnodes)
    )
    return etree.tostring(root)


def _dump_source(source):
    scls = sources.get_source_class(source)
    if scls:
        try:
            data = scls.to_opml(source)
            if data:
                return E.outline(**data)
        except NotImplementedError:
            pass
    return None


def _load(node, group=None):
    for snode in node.findall('outline'):
        ntype = snode.attrib.get('type')
        if ntype == 'rss':
            xmlUrl = snode.attrib.get('xmlUrl')
            if xmlUrl:
                title = snode.attrib.get('title') \
                    or snode.attrib.get('text') \
                    or xmlUrl
                yield (group, title, xmlUrl)
            continue
        ntitle = snode.attrib.get('title')
        if ntitle:
            yield from _load(snode, ntitle)
