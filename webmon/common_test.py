"""
Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import unittest

from . import common


class TestParseInterval(unittest.TestCase):
    def test_sec(self):
        self.assertEqual(common.parse_interval("10"), 10)
        self.assertEqual(common.parse_interval(15), 15)

    def test_min(self):
        self.assertEqual(common.parse_interval("10m"), 10 * 60)
        self.assertEqual(common.parse_interval("99m"), 99 * 60)

    def test_hour(self):
        self.assertEqual(common.parse_interval("10h"), 10 * 60 * 60)
        self.assertEqual(common.parse_interval("99h"), 99 * 60 * 60)

    def test_days(self):
        self.assertEqual(common.parse_interval("10d"), 10 * 60 * 60 * 24)
        self.assertEqual(common.parse_interval("99d"), 99 * 60 * 60 * 24)

    def test_weeks(self):
        self.assertEqual(common.parse_interval("10w"), 10 * 60 * 60 * 24 * 7)
        self.assertEqual(common.parse_interval("99w"), 99 * 60 * 60 * 24 * 7)

    def test_errors(self):
        with self.assertRaises(ValueError):
            common.parse_interval("ladlk")
        with self.assertRaises(ValueError):
            common.parse_interval("-1")
        with self.assertRaises(ValueError):
            common.parse_interval(0)

if __name__ == '__main__':
    unittest.main()
