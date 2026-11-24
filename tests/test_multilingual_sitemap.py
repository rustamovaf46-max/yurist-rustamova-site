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

    def test_no_nested_or_unmatched_paragraphs_in_language_body(self):
        """Guard against malformed generated translations such as <p>...<p>."""
        from html.parser import HTMLParser

        class ParagraphValidator(HTMLParser):
            def __init__(self):
                super().__init__()
                self.open_p = False
                self.problems = []

            def handle_starttag(self, tag, attrs):
                if tag == "p":
                    if self.open_p:
                        self.problems.append("nested <p>")
                    self.open_p = True
                elif tag in {"section", "article", "div", "h1", "h2", "h3", "ul", "ol"} and self.open_p:
                    self.problems.append(f"unclosed <p> before <{tag}>")

            def handle_endtag(self, tag):
                if tag == "p":
                    if not self.open_p:
                        self.problems.append("unmatched </p>")
                    self.open_p = False
                elif tag in {"section", "article", "div", "main"} and self.open_p:
                    self.problems.append(f"unclosed <p> before </{tag}>")

        for lang in sorted(LANGUAGES):
            for page in (ROOT / lang).glob("*.html"):
                with self.subTest(page=str(page.relative_to(ROOT))):
                    parser = ParagraphValidator()
                    parser.feed(page.read_text(encoding="utf-8"))
                    self.assertFalse(parser.problems, f"{page}: {parser.problems[:8]}")

    def test_reciprocal_hreflang_clusters(self):
        from html.parser import HTMLParser

        class Alternates(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == "link" and "alternate" in a.get("rel", "").split() and a.get("hreflang"):
                    self.links.append((a["hreflang"], a.get("href", "")))

        base = "https://" + HOST + "/"
        for page in sorted((ROOT / "en").glob("*.html")):
            slug = page.name
            expected = {"ru": base + slug, "x-default": base + slug}
            expected.update({lang: base + lang + "/" + slug for lang in LANGUAGES})
            for target in [ROOT / slug] + [ROOT / lang / slug for lang in sorted(LANGUAGES)]:
                with self.subTest(page=str(target.relative_to(ROOT))):
                    self.assertTrue(target.is_file())
                    parser = Alternates()
                    parser.feed(target.read_text(encoding="utf-8"))
                    self.assertEqual(len(parser.links), len(expected), str(target))
                    self.assertEqual(dict(parser.links), expected, str(target))

    def test_sitemap_alternates_include_reciprocal_x_default(self):
        tree = ElementTree.parse(ROOT / "sitemap.xml")
        entries = {}
        for node in tree.findall(".//{*}url"):
            loc = node.find("{*}loc")
            links = [(link.get("hreflang"), link.get("href"))
                     for link in node.findall("{http://www.w3.org/1999/xhtml}link")
                     if link.get("rel") == "alternate"]
            entries[(loc.text or "").strip()] = links
        for url, links in entries.items():
            if not links:
                continue
            with self.subTest(url=url):
                mapping = dict(links)
                self.assertEqual(len(links), 5)
                self.assertEqual(set(mapping), {"ru", "en", "zh", "ar", "x-default"})
                self.assertEqual(mapping["x-default"], mapping["ru"])
                self.assertIn(url, mapping.values())
                for alternate in mapping.values():
                    self.assertIn(alternate, entries)
                    self.assertEqual(dict(entries[alternate]), mapping)

    def test_language_direction_and_basic_accessibility_of_translations(self):
        """Check document language, Arabic RTL, content landmark and accessible images.

        This is a source-level gate; WCAG 2.2 AA still needs browser/AT testing.
        """
        from html.parser import HTMLParser

        class Structure(HTMLParser):
            def __init__(self):
                super().__init__()
                self.html_attrs = {}
                self.mains = 0
                self.h1 = 0
                self.issues = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "html":
                    self.html_attrs = attrs
                elif tag == "main":
                    self.mains += 1
                elif tag == "h1":
                    self.h1 += 1
                elif tag == "img" and "alt" not in attrs:
                    self.issues.append("image missing alt attribute")
                elif tag == "a" and attrs.get("target") == "_blank":
                    if "noopener" not in attrs.get("rel", "").split():
                        self.issues.append("target blank without noopener")

        for lang in sorted(LANGUAGES):
            for page in sorted((ROOT / lang).glob("*.html")):
                with self.subTest(page=str(page.relative_to(ROOT))):
                    html = page.read_text(encoding="utf-8")
                    parser = Structure()
                    parser.feed(html)
                    self.assertEqual(parser.html_attrs.get("lang"), lang)
                    if lang == "ar":
                        self.assertEqual(parser.html_attrs.get("dir"), "rtl",
                                         "Arabic content must use right-to-left direction")
                    else:
                        self.assertNotEqual(parser.html_attrs.get("dir"), "rtl")
                    self.assertEqual(parser.mains, 1, "One main landmark required")
                    self.assertEqual(parser.h1, 1, "Exactly one primary heading required")
                    self.assertFalse(parser.issues, f"{page}: {parser.issues}")
                    self.assertIn('/privacy-policy.html', html,
                                  "Link to original Russian privacy policy is required")

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
