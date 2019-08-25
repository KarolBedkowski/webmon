#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 Karol Będkowski <Karol Będkowski@kntbk>
#
# Distributed under terms of the GPLv3 license.

"""
Tests for formattes module
"""


import unittest

from . import formatters


class TestCleanHtmlBrutal(unittest.TestCase):
    def test_clean_body(self):
        content = "aaa <body> ss </body> aa"
        result = formatters._clean_html_brutal(content)
        self.assertEqual(" ss ", result)
        content = "<body> ss </body>"
        result = formatters._clean_html_brutal(content)
        self.assertEqual(" ss ", result)
        content = "<body> ss"
        result = formatters._clean_html_brutal(content)
        self.assertEqual(" ss", result)

    def test_clean_scripts(self):
        content = "aaa <script sss /> bbbb"
        result = formatters._clean_html_brutal(content)
        self.assertEqual("aaa  bbbb", result)
        content = "aaa <script sss> dakakda </script> bbbb"
        result = formatters._clean_html_brutal(content)
        self.assertEqual("aaa  bbbb", result)
