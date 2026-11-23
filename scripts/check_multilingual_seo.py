#!/usr/bin/env python3
"""Validate published multilingual source files without network access."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://xn--80aafwvmkbibjcl2m.xn--p1ai"
LANGS = {"ru", "en", "zh", "ar"}
SITEMAP = ROOT / "sitemap.xml"

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.direction = None
        self.canonical = []
        self.alternates = {}
        self.h1 = 0
        self.noindex = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang, self.direction = a.get("lang"), a.get("dir")
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and a.get("name") == "robots":
            self.noindex = "noindex" in a.get("content", "").lower()
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href"))
        elif tag == "link" and a.get("rel") == "alternate" and a.get("hreflang"):
            self.alternates[a["hreflang"]] = a.get("href")

def main():
    errors = []
    xml = ET.parse(SITEMAP).getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
          "x": "http://www.w3.org/1999/xhtml"}
    urls = {}
    for item in xml.findall("s:url", ns):
        loc = item.findtext("s:loc", namespaces=ns)
        if loc in urls:
            errors.append(f"duplicate sitemap URL: {loc}")
        urls[loc] = item
    translated = []
    for url, item in urls.items():
        rel = urlparse(url).path.lstrip("/")
        if not rel.startswith(("en/", "zh/", "ar/")):
            continue
        file = ROOT / rel
        if not file.is_file():
            errors.append(f"missing translated file: {rel}")
            continue
        p = Page()
        p.feed(file.read_text(encoding="utf-8"))
        lang = rel.split("/", 1)[0]
        if p.lang != lang or (lang == "ar" and p.direction != "rtl"):
            errors.append(f"incorrect lang/dir: {rel}")
        if p.canonical != [url] or p.h1 != 1 or p.noindex:
            errors.append(f"canonical/H1/robots invalid: {rel}")
        if not all(code in p.alternates for code in LANGS):
            errors.append(f"incomplete HTML hreflang: {rel}")
        else:
            for code, dest in p.alternates.items():
                if code not in LANGS and code != "x-default":
                    continue
                if dest not in urls:
                    errors.append(f"alternate absent from sitemap: {rel} -> {dest}")
        xml_alts = {(a.get("hreflang"), a.get("href")) for a in item.findall("x:link", ns)}
        for code in LANGS:
            if (code, p.alternates.get(code)) not in xml_alts:
                errors.append(f"sitemap hreflang mismatch: {rel}, {code}")
        translated.append(rel)
    print(f"SITEMAP URLs: {len(urls)}; translated pages: {len(translated)}")
    ru_pages = [p for p in ROOT.glob("*.html") if p.name not in
                {"privacy-policy.html", "kontakty.html", "analytics-consent.html"}]
    print(f"Root HTML files: {len(ru_pages)}; translation coverage is not complete")
    for err in errors:
        print("ERROR:", err, file=sys.stderr)
    if errors:
        sys.exit(1)
    print("PASS: multilingual sitemap and translated-page structure")

if __name__ == "__main__":
    main()
