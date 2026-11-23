"""Guard the publicly published phone and MAX contact route from silent replacement.

This check does not claim that outsiders cannot spoof websites or intercept
communications on a compromised user's device. It prevents accidental or
unauthorized alternate contact destinations from reaching the main branch.
"""
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import urlparse
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "xn--80aafwvmkbibjcl2m.xn--p1ai"
EXPECTED_PHONE = "+79099282398"
EXPECTED_MAX = "https://max.ru/u/f9LHodD0cOJXOThelfL4zEZsDHL2apF2b_WxxjVt948nXhHX6XZt-opsspM"

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.forms = 0
    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if tag.lower() == "a" and "href" in props:
            self.links.append(props)
        if tag.lower() == "form":
            self.forms += 1

class ContactIntegrityTests(unittest.TestCase):
    def test_no_client_capture_or_contact_redirects_in_public_html(self):
        root = ElementTree.parse(ROOT / "sitemap.xml").getroot()
        pages = []
        for node in root.iter():
            if node.tag.endswith("loc") and node.text:
                parsed = urlparse(node.text.strip())
                self.assertEqual(parsed.hostname, DOMAIN)
                path = parsed.path.lstrip("/") or "index.html"
                pages.append(path)
        self.assertEqual(len(pages), len(set(pages)), 'Duplicate sitemap paths')
        self.assertGreaterEqual(len(pages), 52, 'Sitemap lost public pages')
        for path in pages:
            with self.subTest(page=path):
                page = (ROOT / path).read_text("utf-8")
                parser = Links()
                parser.feed(page)
                self.assertEqual(parser.forms, 0, "Unexpected client data collection form")
                contact_count = 0
                for link in parser.links:
                    href = link.get("href", "").strip()
                    if href.lower().startswith("tel:"):
                        number = re.sub(r"[^+\d]", "", href[4:])
                        self.assertEqual(number, EXPECTED_PHONE, "Unexpected phone destination")
                        contact_count += 1
                    if href.lower().startswith(("https://max.ru/", "http://max.ru/", "https://www.max.ru/", "http://www.max.ru/")):
                        self.assertEqual(href, EXPECTED_MAX, "Unexpected MAX account")
                        if link.get("target") == "_blank":
                            rel = (link.get("rel") or "").lower().split()
                            self.assertIn("noopener", rel)
                            self.assertIn("noreferrer", rel)
                        contact_count += 1
                self.assertGreater(contact_count, 0, "A page lacks all phone/MAX contact paths")

if __name__ == "__main__":
    unittest.main()
