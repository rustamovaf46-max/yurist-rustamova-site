"""Regression checks for local navigation without requiring network access."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
import unittest

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PAGES = (
    "semeynye-spory-yurist-moskva.html",
    "zemelnye-spory-yurist-moskva.html",
    "nasledstvennye-spory-yurist-moskva.html",
    "zhilishchnye-spory-yurist-moskva.html",
    "arbitrazhnye-spory-yurist-moskva.html",
    "pensionnye-spory-sfr-sud-moskva.html",
    "voennye-spory-vyplaty-semyam-moskva.html",
)


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.nav_labels = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "nav":
            self.nav_labels.append(attrs.get("aria-label", ""))
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])


def parse_page(path):
    parser = NavigationParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


class NavigationRegressionTests(unittest.TestCase):
    def test_primary_pages_exist(self):
        for page in ("index.html", "predstavitelstvo-v-sude-moskva.html", "sudebnaya-praktika-i-obraztsy.html", *SERVICE_PAGES):
            with self.subTest(page=page):
                self.assertTrue((ROOT / page).is_file())

    def test_service_pages_offer_next_step_navigation(self):
        for page in SERVICE_PAGES:
            with self.subTest(page=page):
                parsed = parse_page(ROOT / page)
                self.assertIn("Навигация по сайту", parsed.nav_labels)
                for target in ("/", "/predstavitelstvo-v-sude-moskva.html", "/sudebnaya-praktika-i-obraztsy.html"):
                    self.assertIn(target, parsed.links)

    def test_home_has_mobile_navigation(self):
        parsed = parse_page(ROOT / "index.html")
        self.assertIn("Мобильная навигация", parsed.nav_labels)
        self.assertIn("Основная навигация", parsed.nav_labels)
        self.assertIn("mobile-nav", parsed.ids)

    def test_local_links_on_all_sitemap_pages_resolve(self):
        sitemap = ElementTree.parse(ROOT / "sitemap.xml").getroot()
        pages = []
        for item in sitemap:
            node = item.find("{*}loc")
            if node is not None and node.text:
                url = urlsplit(node.text.strip())
                self.assertEqual(url.scheme, "https")
                self.assertEqual(url.hostname, "xn--80aafwvmkbibjcl2m.xn--p1ai")
                pages.append(unquote(url.path).lstrip("/") or "index.html")
        self.assertEqual(len(pages), 51)
        self.assertEqual(len(set(pages)), len(pages), "Duplicate URLs in sitemap")
        for page in pages:
            parsed = parse_page(ROOT / page)
            for href in parsed.links:
                url = urlsplit(href)
                if url.scheme or url.netloc or not href.startswith("/") or href.startswith("//"):
                    continue
                local = unquote(url.path).lstrip("/") or "index.html"
                with self.subTest(page=page, href=href):
                    target = (ROOT / local).resolve()
                    self.assertTrue(target.is_relative_to(ROOT), f"{page}: unsafe path {href}")
                    self.assertTrue(target.is_file(), f"{page}: missing {href}")


if __name__ == "__main__":
    unittest.main()
