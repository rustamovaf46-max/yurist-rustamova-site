"""Guard public pages against new lead-capture and script injection paths.

This is a source-repository safeguard, not a guarantee about REG.RU,
the visitor's device, MAX or other third-party infrastructure.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse, unquote
from xml.etree import ElementTree
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = "xn--80aafwvmkbibjcl2m.xn--p1ai"


class PublicSurface(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.alerts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr = {key.lower(): (value or "") for key, value in attrs}
        if tag == "a" and attr.get("href"):
            self.links.append(attr["href"])
        if tag in {"a", "area"} and attr.get("href", "").strip().lower().startswith(("javascript:", "data:", "vbscript:")):
            self.alerts.append("unsafe link protocol")
        if tag in {"a", "area"} and attr.get("target", "").lower() == "_blank":
            rel = set(attr.get("rel", "").lower().split())
            if "noopener" not in rel and "noreferrer" not in rel:
                self.alerts.append("external tab without noopener/noreferrer")
        if tag == "script" and attr.get("src"):
            # Yandex Metrika is injected by the existing consent-gated
            # loader only. No new synchronous external scripts are allowed.
            self.alerts.append("unreviewed script src: " + attr["src"][:140])
        if tag in {"iframe", "frame", "frameset", "object", "embed", "base", "form"}:
            self.alerts.append("unexpected HTML element: " + tag)
        if tag == "meta" and attr.get("http-equiv", "").lower() in {"refresh", "set-cookie"}:
            self.alerts.append("unexpected meta redirect / cookie setter")
        if tag == "input" and attr.get("type", "text").lower() in {"password", "email", "tel", "file", "hidden"}:
            self.alerts.append("unexpected personal-data input: " + attr["type"])


class PublicPageAttackSurfaceTests(unittest.TestCase):
    def test_all_sitemap_pages_have_no_unreviewed_script_or_capture_surface(self):
        sitemap = ElementTree.parse(ROOT / "sitemap.xml").getroot()
        paths = []
        for item in sitemap:
            node = item.find("{*}loc")
            if node is None or not node.text:
                continue
            url = urlparse(node.text.strip())
            self.assertEqual(url.scheme, "https")
            self.assertEqual(url.hostname, HOST)
            relpath = unquote(url.path.lstrip("/") or "index.html")
            local = (ROOT / relpath).resolve()
            self.assertTrue(local.is_relative_to(ROOT), "URL escapes source tree")
            self.assertTrue(local.is_file(), "Missing page " + relpath)
            paths.append(local)
            with self.subTest(page=relpath):
                checker = PublicSurface()
                checker.feed(local.read_text(encoding="utf-8"))
                self.assertEqual(checker.alerts, [], "Unexpected browser injection or interception path")
        self.assertEqual(len(paths), 52)

    def test_home_contact_channels_remain_approved(self):
        home = PublicSurface()
        home.feed((ROOT / "index.html").read_text(encoding="utf-8"))
        phone = "tel:+79099282398"
        max_link = "https://max.ru/u/f9LHodD0cOJXOThelfL4zEZsDHL2apF2b_WxxjVt948nXhHX6XZt-opsspM"
        self.assertIn(phone, home.links, "Main phone contact removed or changed")
        self.assertIn(max_link, home.links, "Main MAX contact removed or changed")
        for href in home.links:
            if href.startswith(("tel:", "sms:", "mailto:")):
                self.assertEqual(href, phone, "Unexpected direct contact destination")
            if urlparse(href).hostname == "max.ru":
                self.assertEqual(href, max_link, "Unexpected MAX contact destination")

    def test_all_public_pages_reject_unapproved_contact_destinations(self):
        phone = "tel:+79099282398"
        max_link = "https://max.ru/u/f9LHodD0cOJXOThelfL4zEZsDHL2apF2b_WxxjVt948nXhHX6XZt-opsspM"
        email = "mailto:missis.sergeewna2016@yandex.ru"
        sitemap = ElementTree.parse(ROOT / "sitemap.xml").getroot()
        for item in sitemap:
            node = item.find("{*}loc")
            if node is None or not node.text:
                continue
            path = unquote(urlparse(node.text.strip()).path.lstrip("/") or "index.html")
            checker = PublicSurface()
            checker.feed((ROOT / path).read_text(encoding="utf-8"))
            for href in checker.links:
                with self.subTest(page=path, href=href):
                    scheme = urlparse(href).scheme.lower()
                    if scheme in {"tel", "sms", "mailto"}:
                        self.assertIn(href, {phone, email}, "Unapproved direct contact destination")
                    if urlparse(href).hostname == "max.ru":
                        self.assertEqual(href, max_link, "Unapproved MAX destination")

    def test_consent_guard_is_the_only_yandex_loader(self):
        script = (ROOT / "analytics-consent.js").read_text(encoding="utf-8")
        self.assertIn("if (started || choice !== 'accepted') return;", script)
        self.assertIn("https://mc.yandex.ru/metrika/tag.js?id=113668938", script)
        self.assertIn("rustamova_analytics_consent_v1", script)


if __name__ == "__main__":
    unittest.main()
