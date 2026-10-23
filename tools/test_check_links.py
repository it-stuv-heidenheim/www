"""Tests for check_links.fetch: what it requests and that no link stops the run.

Run from the repo root:
    python3 -m unittest discover -s tools -p "test_*.py" -v
"""

import http.client
import unittest
from unittest import mock

import check_links


class FakeResponse:
    def __init__(self, url):
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n):
        return b""

    def geturl(self):
        return self.url


class FetchTest(unittest.TestCase):
    def test_a_space_is_requested_the_way_a_browser_sends_it(self):
        requested = []

        def urlopen(req, timeout):
            requested.append(req.full_url)
            return FakeResponse(req.full_url)

        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(check_links.fetch("https://example.org/a b.pdf"), ("ok", ""))
        self.assertEqual(requested, ["https://example.org/a%20b.pdf"])

    def test_an_http_protocol_error_warns_instead_of_crashing(self):
        def urlopen(req, timeout):
            raise http.client.BadStatusLine("garbage")

        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(check_links.fetch("https://example.org/")[0], "warn")


if __name__ == "__main__":
    unittest.main()
