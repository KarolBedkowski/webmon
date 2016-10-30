"""
Copyright (c) Karol Będkowski, 2016

This file is part of webmon.
Licence: GPLv2+
"""

import time
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


class TestParseTimeRanges(unittest.TestCase):
    def test_01_parse_hour_min(self):
        self.assertEqual(common._parse_hour_min("0"), 0)
        self.assertEqual(common._parse_hour_min("12"), 12 * 60)
        self.assertEqual(common._parse_hour_min("24"), 0)
        self.assertEqual(common._parse_hour_min("0:10"), 10)
        self.assertEqual(common._parse_hour_min("1:10"), 60 + 10)
        self.assertEqual(common._parse_hour_min("12:35"), 12 * 60 + 35)
        self.assertEqual(common._parse_hour_min("12:35:23"), 12 * 60 + 35)

    def test_02_parse_hours_range_01(self):
        res = list(common.parse_hours_range("13-14"))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], 13 * 60)
        self.assertEqual(res[0][1], 14 * 60)

        res = list(common.parse_hours_range("0:0-12"))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], 0)
        self.assertEqual(res[0][1], 12 * 60)

        res = list(common.parse_hours_range("01:40-11:35"))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], 1 * 60 + 40)
        self.assertEqual(res[0][1], 11 * 60 + 35)

        res = list(common.parse_hours_range("01:40"))
        self.assertEqual(len(res), 0)

        res = list(common.parse_hours_range("01:40-aaa"))
        self.assertEqual(len(res), 0)

    def test_02_parse_hours_range_02(self):
        res = list(common.parse_hours_range("0:0-12, 01:40-11:35"))
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0][0], 0)
        self.assertEqual(res[0][1], 12 * 60)
        self.assertEqual(res[1][0], 1 * 60 + 40)
        self.assertEqual(res[1][1], 11 * 60 + 35)

    def test_03_check_date_in_trange_01(self):
        now = list(time.localtime())
        print(now)
        tsr = "13-14"
        now[3], now[4] = 12, 13
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 13, 13
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 14, 13
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)

    def test_03_check_date_in_trange_02(self):
        now = list(time.localtime())
        tsr = "23:30 - 1:45"
        now[3], now[4] = 22, 40
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 23, 40
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 0, 40
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 1, 40
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 1, 50
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 6, 50
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)

    def test_03_check_date_in_trange_03(self):
        now = list(time.gmtime())
        tsr = " 04:40-10:50, 11 -12,23:30-2:00"
        now[3], now[4] = 4, 15
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 6, 15
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 10, 55
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 11, 00
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 12, 00
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 12, 1
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 15, 20
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 23, 20
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)
        now[3], now[4] = 23, 30
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 0, 0
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 1, 0
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 2, 0
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), True)
        now[3], now[4] = 2, 15
        self.assertEqual(common.check_date_in_timerange(
            tsr, time.mktime(tuple(now))), False)


if __name__ == '__main__':
    unittest.main()
