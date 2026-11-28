"""Ensure new judicial-archive translations stay discoverable and self-consistent.

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
    "vzyskanie-sudebnyh-rashodov-na-predstavitelya.html",
    "vselenie-v-kvartiru-cherez-sud.html",
    "obespechitelnye-mery-zemelnyj-spor-2026.html",
    "servitut-dlya-prohoda-cherez-sosedniy-uchastok.html",
    "ustranenie-prepyatstv-v-polzovanii-zemelnym-uchastkom.html",
    "ispravlenie-reestrovoy-oshibki-granits-uchastka.html",
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

    def test_new_articles_have_direct_contact_actions(self):
        for slug in SLUGS:
            for lang in LANGUAGES:
                with self.subTest(slug=slug, lang=lang):
                    html = path_for(slug, lang).read_text(encoding="utf-8")
                    self.assertIn('href="tel:+79099282398"', html)
                    self.assertIn(
                        'href="https://max.ru/u/f9LHodD0cOJXOThelfL4zEZsDHL2apF2b_WxxjVt948nXhHX6XZt-opsspM"',
                        html,
                    )

    def test_english_metadata_fits_search_snippets(self):
        # CJK scripts should not be evaluated with English whitespace word counters.
        for slug in SLUGS:
            with self.subTest(slug=slug):
                html = path_for(slug, "en").read_text(encoding="utf-8")
                title = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
                self.assertIsNotNone(title)
                self.assertGreaterEqual(len(title.group(1)), 30)
                self.assertLessEqual(len(title.group(1)), 60)
                description = re.search(
                    r'<meta name="description" content="([^"]*)"', html
                )
                self.assertIsNotNone(description)
                self.assertGreaterEqual(len(description.group(1)), 110)
                self.assertLessEqual(len(description.group(1)), 160)

    def test_fee_recovery_sources_include_contemporaneous_ruling(self):
        slug = "vzyskanie-sudebnyh-rashodov-na-predstavitelya.html"
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                html = path_for(slug, lang).read_text(encoding="utf-8")
                self.assertIn("cons_doc_LAW_547171/", html)
                self.assertIn("vsrf.ru/documents/all/8474", html)

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
