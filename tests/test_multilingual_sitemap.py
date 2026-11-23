"""Ensure all multilingual URLs advertised in sitemap exist in the deploy archive.

This is a repository check, not proof that REG.RU has deployed the files.
"""
from pathlib import Path
from urllib.parse import urlparse, unquote
from xml.etree import ElementTree
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = "xn--80aafwvmkbibjcl2m.xn--p1ai"
LANGUAGES = {"en", "zh", "ar"}


class MultilingualSitemapTest(unittest.TestCase):
    def test_sitemap_multilingual_files_exist_and_are_publishable(self):
        tree = ElementTree.parse(ROOT / "sitemap.xml")
        declared = set()
        for loc in tree.findall(".//{*}loc"):
            value = (loc.text or "").strip()
            url = urlparse(value)
            if url.hostname != HOST:
                continue
            path = unquote(url.path).lstrip("/")
            parts = path.split("/")
            if len(parts) != 2 or parts[0] not in LANGUAGES:
                continue
            self.assertTrue(parts[1].endswith(".html"), value)
            target = ROOT / path
            self.assertTrue(target.is_file(), f"Sitemap URL has no file in deploy archive: {value}")
            self.assertFalse(target.is_symlink(), f"Unsafe symlink: {path}")
            html = target.read_text(encoding="utf-8")
            self.assertIn(f'lang="{parts[0]}"', html, f"Wrong document language: {path}")
            self.assertIn('rel="canonical"', html, f"Missing canonical: {path}")
            self.assertIn(value, html, f"Canonical URL absent: {path}")
            self.assertNotIn('name="robots" content="noindex', html.lower(), path)
            declared.add(path)
        actual = {f"{lang}/{p.name}" for lang in LANGUAGES
                  for p in (ROOT / lang).glob("*.html") if p.is_file()}
        self.assertEqual(declared, actual,
                         f"Multilingual sitemap/file mismatch: missing={sorted(actual-declared)} extra={sorted(declared-actual)}")

    def test_family_law_three_translations_in_deploy_archive(self):
        name = "semeynye-spory-yurist-moskva.html"
        for lang in sorted(LANGUAGES):
            with self.subTest(language=lang):
                page = ROOT / lang / name
                self.assertTrue(page.is_file(), str(page))
                html = page.read_text(encoding="utf-8")
                self.assertIn(f'lang="{lang}"', html)
                self.assertIn(f'/{lang}/{name}', html)


if __name__ == "__main__":
    unittest.main()
