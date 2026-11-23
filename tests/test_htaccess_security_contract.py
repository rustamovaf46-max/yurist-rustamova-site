"""Protect deployed Apache security policy against accidental weakening."""
from pathlib import Path
import unittest

RULES = (Path(__file__).resolve().parents[1] / ".htaccess").read_text(encoding="utf-8")


class ApacheSecurityContractTests(unittest.TestCase):
    def test_managed_security_block_exists_once(self):
        self.assertEqual(RULES.count("# BEGIN ZEUS SECURITY"), 1)
        self.assertEqual(RULES.count("# END ZEUS SECURITY"), 1)

    def test_browser_security_headers_remain_enabled(self):
        for required in (
            'X-Content-Type-Options "nosniff"',
            'X-Frame-Options "DENY"',
            'Referrer-Policy "strict-origin-when-cross-origin"',
            'Content-Security-Policy "frame-ancestors \'none\'; object-src \'none\'; base-uri \'self\'; form-action \'self\'; upgrade-insecure-requests"',
            'Strict-Transport-Security "max-age=15552000"',
        ):
            with self.subTest(rule=required):
                self.assertIn(required, RULES)

    def test_sensitive_file_restrictions_remain_enabled(self):
        for required in (r"\.(git|svn|hg)", r"\.env", "sql|sqlite|db|bak|old", "pem|key|p12|pfx|zip|tar|tgz"):
            with self.subTest(rule=required):
                self.assertIn(required, RULES)


if __name__ == "__main__":
    unittest.main()
