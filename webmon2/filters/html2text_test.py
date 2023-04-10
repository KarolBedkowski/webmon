# pylint: skip-file
# type: ignore
"""
Copyright (c) Karol Będkowski, 2016-2021

This file is part of webmon.\
Licence: GPLv2+
"""

import unittest

from . import html2text


class TestHtml2Text(unittest.TestCase):
    def test_convert_links(self):
        content = "fslkls [fsdlfslk](<http://127.0.0.1/test/item?id=1234>)"
        conv = html2text._convert_links(content, "http://127.0.0.1/")
        self.assertEqual(
            conv, "fslkls [fsdlfslk](<http://127.0.0.1/test/item?id=1234>)"
        )

        content = "fslkls [fsdlfslk](<item?id=1234>)"
        conv = html2text._convert_links(content, "http://127.0.0.1/test/")
        self.assertEqual(
            conv, "fslkls [fsdlfslk](<http://127.0.0.1/test/item?id=1234>)"
        )


if __name__ == "__main__":
    unittest.main()
