"""Fail-closed source checks: do not deploy privacy/security promises without rules.

These tests are static invariants only. Production header verification happens in
scripts/reg-ru-deploy.sh and in the live probe workflow.
"""
from pathlib import Path
import re
import subprocess
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class SiteSecurityTests(unittest.TestCase):
    def test_apache_security_block_is_unique_and_scoped(self):
        source = (ROOT / ".htaccess").read_text("utf-8")
        self.assertEqual(source.count("# BEGIN ZEUS SECURITY"), 1)
        self.assertEqual(source.count("# END ZEUS SECURITY"), 1)
        self.assertIn("Header always set X-Frame-Options \"DENY\"", source)
        self.assertIn("Header always set X-Content-Type-Options \"nosniff\"", source)
        self.assertIn("Header always set Referrer-Policy", source)
        self.assertIn("Header always set Content-Security-Policy", source)
        self.assertIn("frame-ancestors 'none'", source)
        self.assertIn("object-src 'none'", source)
        self.assertIn("Header always set Strict-Transport-Security", source)
        self.assertIn("RewriteRule (^|/)\\.env", source)
        self.assertIn("RewriteRule \\.(sql|sqlite|db|bak|old|", source)
        self.assertNotIn("RewriteRule (^|/)\\.well-known", source)
        self.assertIn("BEGIN ZEUS CANONICAL", source)
        self.assertIn("R=301", source)

    def test_deployer_does_not_ignore_updated_security_rules(self):
        script = (ROOT / "scripts/reg-ru-deploy.sh").read_text("utf-8")
        result = subprocess.run(["sh", "-n", str(ROOT / "scripts/reg-ru-deploy.sh")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("install_security_rules()", script)
        # Regression: enforce exact shell commands, not mere shell syntax.
        expected_markers = (
            "source_begin=$(grep -c '^# BEGIN ZEUS SECURITY$' \"$source_file\" || true)",
            "source_end=$(grep -c '^# END ZEUS SECURITY$' \"$source_file\" || true)",
            "target_begin=$(grep -c '^# BEGIN ZEUS SECURITY$' \"$target_file\" || true)",
            "target_end=$(grep -c '^# END ZEUS SECURITY$' \"$target_file\" || true)",
        )
        for command in expected_markers:
            self.assertEqual(script.count(command), 1, 'Malformed security grep: ' + command)
        self.assertNotIn('SECURITY — записывать ПОСЛЕ', script)
        self.assertIn("install_security_rules\n", script)
        self.assertIn("security_headers_verified=$SECURITY_APPLIED", script)
        self.assertIn("SECURITY_APPLIED=yes", script)
        self.assertIn("security block rolled back", script)
        self.assertIn("sed '/^# BEGIN ZEUS SECURITY$/,/^# END ZEUS SECURITY$/d'", script)
        self.assertIn("grep -q '^x-frame-options: deny'", script)
        self.assertIn("grep -q '^x-content-type-options: nosniff'", script)
        self.assertIn('cp -p "$backup" "$target_file"', script)

    def test_privacy_policy_is_factual_and_consent_unchanged(self):
        policy = (ROOT / "privacy-policy.html").read_text("utf-8")
        for anchor in ('id="security"', 'id="copyright"', 'id="anti-fraud"', 'id="analytics"'):
            self.assertIn(anchor, policy)
        self.assertIn("24.11.2026", policy)
        self.assertIn("113668938", policy)
        self.assertIn("нет общедоступной базы клиентов", policy)
        self.assertIn("технически невозможно", policy)
        self.assertIn("не передаются через его интерфейс", policy)
        self.assertNotIn("<form ", policy.lower())
        self.assertIn("analytics-consent-script", policy)
        self.assertIn("Без аналитики", policy)

    def test_home_has_clear_links_and_not_a_client_form(self):
        home = (ROOT / "index.html").read_text("utf-8")
        self.assertIn("/privacy-policy.html#security", home)
        self.assertIn("/privacy-policy.html#copyright", home)
        self.assertIn("© 2026", home)
        self.assertNotIn("<form ", home.lower())
        self.assertIn("href=\"tel:+79099282398\"", home)
        self.assertIn("https://max.ru/u/", home)

    def test_robots_sitemap_and_date_of_real_changes(self):
        robot = (ROOT / "robots.txt").read_text("utf-8")
        self.assertIn("Allow: /", robot)
        self.assertIn("Sitemap: https://xn--80aafwvmkbibjcl2m.xn--p1ai/sitemap.xml", robot)
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        entries = {}
        count = 0
        for item in root:
            loc = item.find("{*}loc")
            mod = item.find("{*}lastmod")
            if loc is not None:
                count += 1
                self.assertNotIn(loc.text, entries, 'Duplicate sitemap URL')
                entries[loc.text] = mod.text if mod is not None else None
        self.assertEqual(len(entries), count)
        self.assertGreaterEqual(len(entries), 52, 'Sitemap unexpectedly lost existing URLs')
        self.assertEqual(entries["https://xn--80aafwvmkbibjcl2m.xn--p1ai/"], "2026-11-23")
        self.assertEqual(entries["https://xn--80aafwvmkbibjcl2m.xn--p1ai/privacy-policy.html"], "2026-11-24")

if __name__ == "__main__":
    unittest.main()
