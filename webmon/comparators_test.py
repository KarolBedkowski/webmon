#!/usr/bin/env python3
"""
Copyright (c) Karol Będkowski, 2016

This file is part of webmon.\
Licence: GPLv2+
"""

import unittest

from . import common, comparators

_CONTEXT = common.Context({}, None, 0, None, {})


class TestComparatorAdded(unittest.TestCase):
    def test_empty_prev(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4]))
        prev = common.RECORD_SEPARATOR.join(map(str, []))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4])))

    def test_empty_curr(self):
        curr = common.RECORD_SEPARATOR.join(map(str, []))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [])))

    def test_added_1(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [4, 5])))

    def test_added_2(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [2, 3]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [1, 4, 5])))

    def test_added_3(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [2, 4, 5]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [1, 3])))

    def test_added_4(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [2, 4]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [1, 3, 5])))

    def test_added_5(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 6]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [6])))

    def test_added_6(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [6, 7]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        diff = comparators.Added(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [6, 7])))


class TestComparatorDeleted(unittest.TestCase):
    def test_empty_prev(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4]))
        prev = common.RECORD_SEPARATOR.join(map(str, []))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [])))

    def test_empty_curr(self):
        curr = common.RECORD_SEPARATOR.join(map(str, []))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4])))

    def test_deleted_1(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [])))

    def test_deleted_2(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [2, 3]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [])))

    def test_deleted_3(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [2, 4, 5]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [])))

    def test_deleted_4(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [2, 4]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff, common.RECORD_SEPARATOR.join(map(str, [])))

    def test_deleted_5(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 6]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [2, 3, 4, 5])))

    def test_deleted_6(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [6, 7]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(
            diff, common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5])))

    def test_deleted_7(self):
        curr = common.RECORD_SEPARATOR.join(map(str, [1, 5]))
        prev = common.RECORD_SEPARATOR.join(map(str, [1, 2, 3, 4, 5]))
        diff = comparators.Deleted(_CONTEXT).\
            compare(prev, "then", curr, "now")
        self.assertEqual(diff,
                         common.RECORD_SEPARATOR.join(map(str, [2, 3, 4])))

if __name__ == '__main__':
    unittest.main()
