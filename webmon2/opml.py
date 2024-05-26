# Copyright © 2019 Karol Będkowski
#
# Distributed under terms of the GPLv3 license.

"""
Import/export data in opml format.
"""

import itertools
import operator
import typing as ty
from contextlib import suppress
from xml.etree.ElementTree import Element

import structlog
from defusedxml import ElementTree as etree  # noqa: N813
from lxml.builder import E  # pylint: disable=no-name-in-module

from webmon2 import database, model, sources

_LOG: structlog.stdlib.BoundLogger = structlog.getLogger(__name__)


class InvalidFileError(RuntimeError):
    pass


def load_opml(
    content: bytes,
) -> ty.Iterable[ty.Tuple[str, ty.Iterable[ty.Tuple[str, model.Source]]]]:
    root = etree.XML(content)
    if root.tag != "opml":
        raise InvalidFileError("content is not opml")

    body = root.find("body")
    data = sorted(_load(body), key=lambda x: x[0] or "")
    return itertools.groupby(data, operator.itemgetter(0))


def load_data(db: database.DB, content: bytes, user_id: int) -> None:
    for group_name, items in load_opml(content):
        try:
            group = database.groups.find(db, user_id, group_name)
        except database.NotFoundError:
            group = model.SourceGroup(name=group_name, user_id=user_id)
            group = database.groups.save(db, group)
            _LOG.debug("opml: new group: %s", group)

        assert group.id
        group_id: int = group.id
        for _, source in items:
            source.group_id = group_id
            source.user_id = user_id
            src = database.sources.save(db, source)
            _LOG.debug("opml: new source: %s", src)


def dump_data(db: database.DB, user_id: int) -> str:
    groups = database.groups.get_all(db, user_id)
    gnodes = []
    for group in groups:
        items = (
            _dump_source(source)
            for source in database.sources.get_all(db, user_id, group.id)
        )
        if items_filtered := list(filter(lambda x: x is not None, items)):
            gnodes.append(
                E.outline(*items_filtered, text=group.name, title=group.name)
            )

    root = E.opml(E.head(E.title("subscriptions")), E.body(*gnodes))
    return etree.tostring(root)  # type: ignore


def _dump_source(source: model.Source) -> ty.Optional[Element]:
    if scls := sources.get_source_class(source.kind):
        with suppress(NotImplementedError):
            if data := scls.to_opml(source):
                return E.outline(**data)  # type: ignore

    return None


def _load(
    node: Element, group: ty.Optional[str] = None
) -> ty.Iterator[ty.Tuple[str, model.Source]]:
    for snode in node.findall("outline"):
        if ntype := snode.attrib.get("type"):
            if scls := sources.get_source_class(ntype):
                try:
                    if source := scls.from_opml(snode.attrib):
                        yield (group or "", source)

                except NotImplementedError:
                    _LOG.warning("opml: import %s not supported", ntype)

                except ValueError as err:
                    _LOG.info(
                        "opml: import error from attrib",
                        attrib=snode.attrib,
                        error=err,
                    )

            continue

        if ntitle := snode.attrib.get("title"):
            yield from _load(snode, ntitle)
