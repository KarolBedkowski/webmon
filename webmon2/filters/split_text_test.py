#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2021 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.
# pylint: skip-file
# type: ignore

"""

"""


import unittest

from webmon2 import model

from . import split_text


class TestGetElementsByXpath(unittest.TestCase):
    def test_fitler1(self):
        entry = model.Entry()
        entry.content = """<foo><bar>test1</bar><bar>test2</bar></foo>"""

        flr = split_text.GetElementsByXpath(config={"xpath": "//foo/bar"})

        elems = list(flr._filter(entry))
        self.assertEqual(len(elems), 2)
        self.assertEqual(elems[0].content, "<bar>test1</bar>")
        self.assertEqual(elems[1].content, "<bar>test2</bar>")


class TestGetElementsByCss(unittest.TestCase):
    def test_fitler1(self):
        entry = model.Entry()
        entry.content = (
            '<foo><bar id="a1">test1</bar><bar id="a2">test2</bar></foo>'
        )

        flr = split_text.GetElementsByCss(config={"sel": "#a2"})
        flr.validate()

        elems = list(flr._filter(entry))
        self.assertEqual(len(elems), 1)
        self.assertEqual(elems[0].content, '<bar id="a2">test2</bar>')

    def test_fitler2(self):
        entry = model.Entry()
        entry.content = (
            '<foo><bar id="a1">test1</bar><bar id="a2">test2</bar></foo>'
        )

        flr = split_text.GetElementsByCss(config={"sel": "bar#a2"})
        flr.validate()

        elems = list(flr._filter(entry))
        self.assertEqual(len(elems), 1)
        self.assertEqual(elems[0].content, '<bar id="a2">test2</bar>')

    def test_fitler3(self):
        entry = model.Entry()
        entry.content = (
            '<foo><bar id="a1">test1</bar><bar id="a2">test2</bar></foo>'
        )

        flr = split_text.GetElementsByCss(config={"sel": "bar"})
        flr.validate()

        elems = list(flr._filter(entry))
        self.assertEqual(len(elems), 2)
        self.assertEqual(elems[0].content, '<bar id="a1">test1</bar>')
        self.assertEqual(elems[1].content, '<bar id="a2">test2</bar>')


class TestGetElementsById(unittest.TestCase):
    def test_filter1(self):
        entry = model.Entry()
        entry.content = (
            '<foo><bar id="a1">test1</bar><bar id="a2">test2</bar></foo>'
        )

        flr = split_text.GetElementsById(config={"sel": "a2"})

        elems = list(flr._filter(entry))
        self.assertEqual(len(elems), 1)
        self.assertEqual(elems[0].content, '<bar id="a2">test2</bar>')


if __name__ == "__main__":
    unittest.main()
