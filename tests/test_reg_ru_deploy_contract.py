"""Guard the public REG.RU deployment heartbeat against accidental removal."""
from pathlib import Path
import unittest

SCRIPT = (Path(__file__).resolve().parents[1] / "scripts/reg-ru-deploy.sh").read_text(encoding="utf-8")


class RegRuDeployContractTests(unittest.TestCase):
    def test_heartbeat_contains_live_file_fingerprints(self):
        for name in ("published_at_utc", "sitemap_url_count", "sitemap_checksum",
                     "homepage_checksum", "privacy_policy_checksum",
                     "updated_files", "security_headers_verified"):
            with self.subTest(field=name):
                self.assertIn('echo "' + name + '=$', SCRIPT)

    def test_fingerprints_come_from_published_site_not_archive(self):
        for file in ("sitemap.xml", "index.html", "privacy-policy.html"):
            with self.subTest(file=file):
                self.assertIn('cksum "$SITE_DIR/' + file + '"', SCRIPT)

    def test_heartbeat_is_written_after_publication(self):
        self.assertLess(SCRIPT.index('publish_file "$SRC_DIR/$INDEXNOW_KEY.txt"'),
                        SCRIPT.index('HEALTH_TMP=$(mktemp'))
        self.assertLess(SCRIPT.index('install_security_rules\n'),
                        SCRIPT.index('HEALTH_TMP=$(mktemp'))


if __name__ == "__main__":
    unittest.main()
