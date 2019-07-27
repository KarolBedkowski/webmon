#!/usr/bin/env python3
# pylint: skip-file
"""
Copyright (c) Karol Będkowski, 2016-2019

This file is part of webmon.\
Licence: GPLv2+
"""
# pylint: skip-file

import unittest

from . import score


class TestScore(unittest.TestCase):
    def test_score_many(self):
        conf = {
            "patterns": "rust;python;go",
            "score_change": 1,
            "match_many": True,
        }
        sco = score.Score(conf)
        self.assertEqual(3, sco._score_for_content(
            "python rust go go"
        ))
        self.assertEqual(1, sco._score_for_content(
            "pyeethon rsust go go"
        ))
        self.assertEqual(0, sco._score_for_content(
            "pyeethon rsust gg2o"
        ))

    def test_score_one(self):
        conf = {
            "patterns": "rust;python;go",
            "score_change": 1,
            "match_many": False,
        }
        sco = score.Score(conf)
        self.assertEqual(1, sco._score_for_content(
            "python rust go go"
        ))
        self.assertEqual(1, sco._score_for_content(
            "pyeethon rsust go go"
        ))
        self.assertEqual(0, sco._score_for_content(
            "pyeethon rsust gg2o"
        ))

    def test_score_manu_multiple(self):
        conf = {
            "patterns": "rust;python;go",
            "score_change": 1,
            "match_many": True,
        }
        sco = score.Score(conf)
        self.assertEqual(3, sco._score_for_content(
            "python rust go go",
            "rust",
        ))
        self.assertEqual(3, sco._score_for_content(
            "python go go",
            "rust",
        ))
        self.assertEqual(2, sco._score_for_content(
            "python g2",
            "rust",
        ))


if __name__ == '__main__':
    unittest.main()
