#!/usr/bin/env python3
"""
Copyright (c) Karol Będkowski, 2016

This file is part of webmon.\
Licence: GPLv2+
"""

import unittest

from . import common, filters

_CONTEXT = common.Context({}, None, 0, None, {})


class TestFilterWrap(unittest.TestCase):
    def test_wrap_simple(self):
        conf = {'width': 10, 'max_lines': 10}
        fltr = filters.Wrap(conf, _CONTEXT)
        inp = "123456 123456 123 1234567"
        exp = '123456\n123456 123\n1234567'
        res = fltr._wrap_line_keep_indent(inp)
        self.assertEqual(res, exp)

    def test_wrap_keep_indent(self):
        conf = {'width': 10, 'max_lines': 10}
        fltr = filters.Wrap(conf, _CONTEXT)
        inp = "   123456 123456 123 1234567"
        exp = '   123456\n   123456\n   123\n   1234567'
        res = fltr._wrap_line_keep_indent(inp)
        self.assertEqual(res, exp)

    def test_wrap_max_lines(self):
        conf = {'width': 10, 'max_lines': 3}
        fltr = filters.Wrap(conf, _CONTEXT)
        inp = "123456 123456 1234567 123456 123456"
        exp = '123456\n123456\n[...]'
        res = fltr._wrap_line_keep_indent(inp)
        self.assertEqual(res, exp)


class TestFilterGrep(unittest.TestCase):
    def test_grep_parts(self):
        conf = {'pattern': r'.*123.*', 'mode': 'parts'}
        fltr = filters.Grep(conf, _CONTEXT)
        res = common.Result(None)
        res.items = ['aa\n1234\nbb', 'ww\n234\nddd', '123\ndsdsd']
        exp = ['aa\n1234\nbb', '123\ndsdsd']
        out = fltr.filter(res).items
        self.assertEqual(out, exp)

    def test_grep_lines(self):
        conf = {'pattern': r'.*123.*', 'mode': 'lines'}
        fltr = filters.Grep(conf, _CONTEXT)
        res = common.Result(None)
        res.items = ['aa\n1234\nbb', 'ww\n234\nddd', '123\ndsdsd']
        exp = ['1234', '123']
        out = fltr.filter(res).items
        self.assertEqual(out, exp)

if __name__ == '__main__':
    unittest.main()
