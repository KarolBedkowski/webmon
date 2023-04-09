# Copyright © 2023 Karol Będkowski <Karol Będkowski@kkomp>
#
# Distributed under terms of the GPLv3 license.

"""

"""
import unittest
from unittest import mock
from urllib.parse import urljoin
from datetime import datetime, timezone

from freezegun import freeze_time

from . import _filters as F


class TestProxyUrl(unittest.TestCase):
    @mock.patch("webmon2.web._filters._create_proxy_url")
    def test_srcset(self, _create_proxy_url):
        # prevent calling url_for
        _create_proxy_url.side_effect = lambda x, y: urljoin(y, x)

        base = "http://foo/bar/"

        self.assertEqual(
            F._create_proxy_url("abc/aa", base), "http://foo/bar/abc/aa"
        )

        self.assertEqual(
            ",".join(F._create_proxy_urls_srcset("/abc/image.txt", base)),
            "http://foo/abc/image.txt",
        )

        self.assertEqual(
            ",".join(F._create_proxy_urls_srcset("abc/image.txt", base)),
            "http://foo/bar/abc/image.txt",
        )

        self.assertEqual(
            ",".join(F._create_proxy_urls_srcset(" /abc/image.txt", base)),
            " http://foo/abc/image.txt",
        )

        self.assertEqual(
            ",".join(
                F._create_proxy_urls_srcset(" /abc/image.txt, abc.jpg", base)
            ),
            " http://foo/abc/image.txt, http://foo/bar/abc.jpg",
        )

        self.assertEqual(
            ",".join(
                F._create_proxy_urls_srcset(
                    "/abc/image.txt 123x23, abc.jpg 12x23", base
                )
            ),
            "http://foo/abc/image.txt 123x23, http://foo/bar/abc.jpg 12x23",
        )


class TestAgeFilter(unittest.TestCase):
    @freeze_time("2023-01-02 03:04:05")
    def test_age_filter1(self):
        self.assertEqual(F._age_filter(None), "")

        tzone = timezone.utc

        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 3, 4, 5, tzinfo=tzone)), "<1m"
        )
        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 3, 4, 0, tzinfo=tzone)), "<1m"
        )
        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 3, 3, 6, tzinfo=tzone)), "<1m"
        )

        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 3, 3, 5, tzinfo=tzone)), "1m"
        )

        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 3, 3, 0, tzinfo=tzone)), "1m"
        )
        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 3, 2, 0, tzinfo=tzone)), "2m"
        )

        self.assertEqual(
            F._age_filter(datetime(2023, 1, 2, 2, 2, 0, tzinfo=tzone)), "1h"
        )
        self.assertEqual(
            F._age_filter(datetime(2023, 1, 1, 4, 3, 0, tzinfo=tzone)), "23h"
        )

        self.assertEqual(
            F._age_filter(datetime(2023, 1, 1, 2, 3, 0, tzinfo=tzone)), "1d"
        )
        self.assertEqual(
            F._age_filter(datetime(2022, 12, 31, 1, 3, 0, tzinfo=tzone)), "2d"
        )


class PostfixPrefix(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(F._extract_prefix_postfix(""), ("", 0, 0))
        self.assertEqual(F._extract_prefix_postfix(" "), ("", 1, 0))
        self.assertEqual(F._extract_prefix_postfix("a"), ("a", 0, 0))
        self.assertEqual(F._extract_prefix_postfix("a b c"), ("a b c", 0, 0))
        self.assertEqual(F._extract_prefix_postfix(" a"), ("a", 1, 0))
        self.assertEqual(F._extract_prefix_postfix("  abc"), ("abc", 2, 0))
        self.assertEqual(F._extract_prefix_postfix("  abc "), ("abc", 2, 1))
        self.assertEqual(
            F._extract_prefix_postfix("  a b c  "), ("a b c", 2, 2)
        )
        self.assertEqual(F._extract_prefix_postfix("a b c  "), ("a b c", 0, 2))

    def test_apply(self):
        self.assertEqual(F._apply_prefix_postfix("", 0, 0), "")
        self.assertEqual(F._apply_prefix_postfix("", 1, 0), " ")
        self.assertEqual(F._apply_prefix_postfix("", 0, 1), " ")
        self.assertEqual(F._apply_prefix_postfix("", 1, 2), "   ")
        self.assertEqual(F._apply_prefix_postfix("abc", 0, 0), "abc")
        self.assertEqual(F._apply_prefix_postfix("abc", 1, 0), " abc")
        self.assertEqual(F._apply_prefix_postfix("abc", 0, 1), "abc ")
        self.assertEqual(F._apply_prefix_postfix("abc", 1, 2), " abc  ")
        self.assertEqual(F._apply_prefix_postfix("abc", 3, 2), "   abc  ")
