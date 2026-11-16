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


    def test_temporary_504_retries_and_succeeds(self):
        from io import BytesIO
        from unittest.mock import MagicMock
        from urllib.error import HTTPError
        failure = HTTPError(yw.API + "/user", 504, "Gateway Timeout", {}, BytesIO(b""))
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"user_id":42}'
        with patch.dict(os.environ, {"YANDEX_WEBMASTER_TOKEN": "test-token"}):
            with patch.object(yw, "urlopen", side_effect=[failure, response]) as open_mock:
                with patch.object(yw.time, "sleep") as sleep_mock:
                    self.assertEqual(yw.request("GET", "/user"), {"user_id": 42})
                    self.assertEqual(open_mock.call_count, 2)
                    sleep_mock.assert_called_once_with(1)

    def test_auth_403_never_retries(self):
        from io import BytesIO
        from urllib.error import HTTPError
        failure = HTTPError(yw.API + "/user", 403, "Forbidden", {}, BytesIO(b'{}'))
        with patch.dict(os.environ, {"YANDEX_WEBMASTER_TOKEN": "test-token"}):
            with patch.object(yw, "urlopen", side_effect=failure) as open_mock:
                with patch.object(yw.time, "sleep") as sleep_mock:
                    with self.assertRaisesRegex(yw.ApiError, "403"):
                        yw.request("GET", "/user")
                    open_mock.assert_called_once()
                    sleep_mock.assert_not_called()



if __name__ == "__main__":
    unittest.main()
