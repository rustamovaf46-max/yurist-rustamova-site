"""Ensure public author attribution agrees with the site's verified Person profile."""
import json
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUTHOR_ID = "https://xn--80aafwvmkbibjcl2m.xn--p1ai/#fatima"
BIO = "/o-yuriste-fatima-rustamova.html"
ARTICLES = (
    "opredelenie-mesta-zhitelstva-rebenka-cherez-sud.html",
    "poryadok-polzovaniya-kvartiroy.html",
    "vselenie-v-kvartiru-cherez-sud.html",
)


class JsonLdScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.chunks = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.active = True
            self.chunks = []

    def handle_data(self, text):
        if self.active:
            self.chunks.append(text)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.scripts.append(json.loads("".join(self.chunks)))
            self.active = False


class VerifiedAuthorIdentityTest(unittest.TestCase):
    def test_indexed_article_author_is_consistent_with_profile(self):
        self.assertTrue((ROOT / BIO.lstrip("/")).is_file())
        for name in ARTICLES:
            with self.subTest(article=name):
                source = (ROOT / name).read_text("utf-8")
                self.assertIn('href="' + BIO + '"', source)
                parser = JsonLdScripts()
                parser.feed(source)
                nodes = []
                for item in parser.scripts:
                    nodes.extend(item.get("@graph", [item]))
                articles = [n for n in nodes if n.get("@type") in ("Article", "WebPage")]
                self.assertTrue(articles, "Missing article/page schema")
                for n in articles:
                    self.assertEqual(n.get("author", {}).get("@id"), AUTHOR_ID)
                    if n.get("publisher"):
                        self.assertEqual(n["publisher"].get("@id"), AUTHOR_ID)


if __name__ == "__main__":
    unittest.main()
