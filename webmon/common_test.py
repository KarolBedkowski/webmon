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


class TestApplyDefaults(unittest.TestCase):
    def test_empty_defaults(self):
        defaults = {}
        conf = {
            "a": "a",
            "b": [1, [1, 2, 3], {"12": 12}],
            "c": {
                "c1": 123,
                "c2": 234,
                "c3": [1, 2, 3, 4, 5],
                "c5": {"a1": "a1"}
            }
        }
        res = common.apply_defaults(defaults, conf)
        self.assertDictEqual(res, conf)

    def test_noempty_defaults(self):
        defaults = {
            "a": "123",
            "c": {
                "c5": {
                    "a1": "a0",
                    "a2": "a2",
                },
                "c6": [1, 2, 3],
            },
            "d": 12,
        }
        conf = {
            "a": "a",
            "b": [1, [1, 2, 3], {"12": 12}],
            "c": {
                "c1": 123,
                "c2": 234,
                "c3": [1, 2, 3, 4, 5],
                "c5": {"a1": "a1"}
            }
        }
        res = common.apply_defaults(defaults, conf)
        self.assertEqual(res["a"], "a")
        self.assertEqual(res["b"], [1, [1, 2, 3], {"12": 12}])
        self.assertEqual(res["c"]["c1"], 123)
        self.assertEqual(res["c"]["c2"], 234)
        self.assertEqual(res["c"]["c3"], [1, 2, 3, 4, 5])
        self.assertEqual(res["c"]["c5"]["a1"], "a1")
        self.assertEqual(res["c"]["c5"]["a2"], "a2")
        self.assertEqual(res["c"]["c6"], [1, 2, 3])
        self.assertEqual(res["d"], 12)


if __name__ == '__main__':
    unittest.main()
