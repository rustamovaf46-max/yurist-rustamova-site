"""Regression checks for evidence-based public author identity and AI discovery.

This is a source-level contract, not a claim of indexing or AI recommendation.
Article coverage is deliberately limited to already verified author-linked
pages; expanding it is separate from proving new professional credentials.
"""
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://xn--80aafwvmkbibjcl2m.xn--p1ai"
PROFILE_PATH = "o-yuriste-fatima-rustamova.html"
PROFILE_URL = ORIGIN + "/" + PROFILE_PATH
PERSON_ID = ORIGIN + "/#fatima"
CURATED_ARTICLES = (
    "vselenie-v-kvartiru-cherez-sud.html",
    "otmena-sudebnogo-prikaza-za-zhku.html",
    "vzyskanie-sudebnyh-rashodov-na-predstavitelya.html",
    "zevs-avtonomnyy-ii-upravlyayushchiy-biznesom.html",
)


def json_ld_nodes(html):
    scripts = re.findall(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.I | re.S,
    )
    for body in scripts:
        data = json.loads(body)
        objects = data if isinstance(data, list) else [data]
        for node in objects:
            if not isinstance(node, dict):
                continue
            for item in node.get("@graph", [node]):
                if isinstance(item, dict):
                    yield item


def types(node):
    value = node.get("@type", "")
    return set(value if isinstance(value, list) else [value])


class PublicAuthorIdentityTests(unittest.TestCase):
    def test_profile_page_references_single_person_identity(self):
        page = (ROOT / PROFILE_PATH).read_text(encoding="utf-8")
        self.assertIn(f'<link rel="canonical" href="{PROFILE_URL}"', page)
        self.assertIn("Фатима Рустамова", page)
        profile = next(
            (node for node in json_ld_nodes(page) if "ProfilePage" in types(node)),
            None,
        )
        self.assertIsNotNone(profile, "Professional profile must use ProfilePage JSON-LD")
        person = profile.get("mainEntity")
        self.assertIsInstance(person, dict, "ProfilePage mainEntity must be a Person")
        self.assertIn("Person", types(person))
        self.assertEqual(person.get("@id"), PERSON_ID)
        self.assertIn("Рустамова", person.get("name", ""))
        self.assertEqual(person.get("url"), ORIGIN + "/")

    def test_existing_author_linked_articles_have_same_id(self):
        for path in CURATED_ARTICLES:
            with self.subTest(article=path):
                html = (ROOT / path).read_text(encoding="utf-8")
                articles = [
                    node for node in json_ld_nodes(html)
                    if "Article" in types(node) or "BlogPosting" in types(node)
                ]
                self.assertTrue(articles, "No Article JSON-LD found")
                for article in articles:
                    author = article.get("author")
                    self.assertIsInstance(author, dict)
                    self.assertIn("Person", types(author))
                    self.assertEqual(author.get("@id"), PERSON_ID)
                    self.assertEqual(author.get("url"), PROFILE_URL)

    def test_llms_txt_links_are_public_sitemap_pages(self):
        # llms.txt is optional guidance, not an indexing protocol.
        guidance = (ROOT / "llms.txt").read_text(encoding="utf-8")
        urls = re.findall(r'\]\((https://[^)]+)\)', guidance)
        self.assertTrue(urls, "Public AI discovery guide is empty")
        sitemap = ElementTree.parse(ROOT / "sitemap.xml").getroot()
        published = {
            loc.text for loc in sitemap.iter()
            if loc.tag.endswith("loc") and loc.text
        }
        for url in urls:
            with self.subTest(url=url):
                parsed = urlparse(url)
                self.assertEqual(parsed.netloc, urlparse(ORIGIN).netloc)
                if parsed.path == "/sitemap.xml":
                    # The sitemap is a public machine-readable resource, not a page
                    # that should list itself inside the sitemap.
                    self.assertTrue((ROOT / "sitemap.xml").is_file())
                else:
                    self.assertIn(url, published, "Public guide points to an unlisted page")
        self.assertNotRegex(guidance, r'(?i)api[_-]?key|bearer\s+[a-z0-9]|password=')


if __name__ == "__main__":
    unittest.main()
