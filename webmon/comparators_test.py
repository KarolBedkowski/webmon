"""
Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import unittest

from . import common, comparators

_CONTEXT = common.Context({}, None, 0, None, {})


class TestComparatorAdded(unittest.TestCase):
    def test_empty_prev(self):
        curr = [1, 2, 3, 4]
        prev = []
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [1, 2, 3, 4])

    def test_empty_curr(self):
        curr = []
        prev = [1, 2, 3, 4]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [])

    def test_added_1(self):
        curr = [1, 2, 3, 4, 5]
        prev = [1, 2, 3]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [4, 5])

    def test_added_2(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 3]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [1, 4, 5])

    def test_added_3(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4, 5]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [1, 3])

    def test_added_4(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [1, 3, 5])

    def test_added_5(self):
        curr = [1, 6]
        prev = [1, 2, 3, 4, 5]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [6])

    def test_added_6(self):
        curr = [6, 7]
        prev = [1, 2, 3, 4, 5]
        diff = list(comparators.Added(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [6, 7])


class TestComparatorDeleted(unittest.TestCase):
    def test_empty_prev(self):
        curr = [1, 2, 3, 4]
        prev = []
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [])

    def test_empty_curr(self):
        curr = []
        prev = [1, 2, 3, 4]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [1, 2, 3, 4])

    def test_deleted_1(self):
        curr = [1, 2, 3, 4, 5]
        prev = [1, 2, 3]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [])

    def test_deleted_2(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 3]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [])

    def test_deleted_3(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4, 5]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [])

    def test_deleted_4(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [])

    def test_deleted_5(self):
        curr = [1, 6]
        prev = [1, 2, 3, 4, 5]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [2, 3, 4, 5])

    def test_deleted_6(self):
        curr = [6, 7]
        prev = [1, 2, 3, 4, 5]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [1, 2, 3, 4, 5])

    def test_deleted_7(self):
        curr = [1, 5]
        prev = [1, 2, 3, 4, 5]
        diff = list(comparators.Deleted(_CONTEXT).
                    compare(prev, None, curr, None))
        self.assertEqual(diff, [2, 3, 4])

if __name__ == '__main__':
    unittest.main()
