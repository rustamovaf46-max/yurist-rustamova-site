import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import yandex_webmaster as yw


class YandexOwnerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.verified = [{"host_id": "https:xn--80aafwvmkbibjcl2m.xn--p1ai:443",
                          "ascii_host_url": yw.SITE, "verified": True}]

    def test_missing_token_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(yw.ApiError):
                yw.request("GET", "/user")

    def test_http_only_is_not_considered_verified_https(self):
        http = [{"host_id": "http:xn--80aafwvmkbibjcl2m.xn--p1ai:80",
                 "ascii_host_url": yw.SITE.replace("https:", "http:"), "verified": True}]
        with self.assertRaises(yw.ApiError):
            yw.select_https(http)

    def test_cross_domain_recrawl_refused(self):
        with self.assertRaises(yw.ApiError):
            yw.execute(1, self.verified, "recrawl", ["https://example.org/"], True)

    def test_http_recrawl_refused(self):
        with self.assertRaises(yw.ApiError):
            yw.execute(1, self.verified, "recrawl", [yw.SITE.replace("https:", "http:")], True)

    def test_unverified_recrawl_refused(self):
        hosts = [{**self.verified[0], "verified": False}]
        with self.assertRaises(yw.ApiError):
            yw.execute(1, hosts, "recrawl", [yw.SITE], True)

    def test_recrawl_dry_run_never_calls_api(self):
        with patch.object(yw, "request") as req:
            self.assertEqual(yw.execute(1, self.verified, "recrawl", [yw.SITE], False), 0)
            req.assert_not_called()


if __name__ == "__main__":
    unittest.main()
