"""Ensure judicial land-archive translations stay discoverable and self-consistent.

These are repository checks, not proof of deployment or indexing on REG.RU.
"""
from pathlib import Path
from xml.etree import ElementTree
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://xn--80aafwvmkbibjcl2m.xn--p1ai"
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
XHTML_NS = "{http://www.w3.org/1999/xhtml}"
SLUGS = (
    "servitut-dlya-prohoda-cherez-sosedniy-uchastok.html",
    "ustranenie-prepyatstv-v-polzovanii-zemelnym-uchastkom.html",
)
LANGUAGES = ("ru", "en", "zh", "ar")


def path_for(slug, lang):
    return ROOT / (slug if lang == "ru" else f"{lang}/{slug}")


def url_for(slug, lang):
    return BASE + "/" + (slug if lang == "ru" else f"{lang}/{slug}")


class MultilingualLandArchiveTests(unittest.TestCase):
    def test_each_language_is_a_real_article_with_self_canonical(self):
        for slug in SLUGS:
            for lang in LANGUAGES:
                with self.subTest(slug=slug, lang=lang):
                    path = path_for(slug, lang)
                    self.assertTrue(path.is_file(), f"Missing translated file {path}")
                    html = path.read_text(encoding="utf-8")
                    self.assertGreater(len(html), 2000, "Empty or stub article")
                    self.assertIn(f'<html lang="{lang}"', html)
                    self.assertRegex(html, r"<h1(?:\s[^>]*)?>.+?</h1>")
                    self.assertIn(f'<link rel="canonical" href="{url_for(slug, lang)}">', html)
                    if lang == "ar":
                        self.assertIn('dir="rtl"', html)
                    for other in LANGUAGES:
                        self.assertIn(f'hreflang="{other}" href="{url_for(slug, other)}"', html)
                    self.assertIn(f'hreflang="x-default" href="{url_for(slug, "ru")}"', html)

    def test_sitemap_has_unique_locales_and_reciprocal_alternates(self):
        tree = ElementTree.parse(ROOT / "sitemap.xml")
        entries = tree.findall(f"{SITEMAP_NS}url")
        urls = [
            entry.findtext(f"{SITEMAP_NS}loc", default="")
            for entry in entries
        ]
        self.assertEqual(len(urls), len(set(urls)), "Duplicate loc URLs in sitemap")
        for slug in SLUGS:
            expected_alternates = {
                **{lang: url_for(slug, lang) for lang in LANGUAGES},
                "x-default": url_for(slug, "ru"),
            }
            for lang in LANGUAGES:
                with self.subTest(slug=slug, lang=lang):
                    page_url = url_for(slug, lang)
                    self.assertEqual(urls.count(page_url), 1)
                    entry = entries[urls.index(page_url)]
                    alternates = {
                        el.attrib.get("hreflang"): el.attrib.get("href")
                        for el in entry.findall(f"{XHTML_NS}link")
                    }
                    self.assertEqual(alternates, expected_alternates)

    def test_library_exposes_translations(self):
        library = (ROOT / "sudebnaya-praktika-i-obraztsy.html").read_text(
            encoding="utf-8"
        )
        for slug in SLUGS:
            with self.subTest(slug=slug):
                self.assertIn(f'href="/{slug}"', library)
                for lang in ("en", "zh", "ar"):
                    self.assertIn(f'href="/{lang}/{slug}"', library)


if __name__ == "__main__":
    unittest.main()
