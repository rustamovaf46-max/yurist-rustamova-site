#!/usr/bin/env python3
"""ZEUS: deterministic SEO checks for all published static pages.

Read-only. Does not edit HTML, analytics, sitemap, or deployment.
Exit 1 for errors and publish Markdown to GitHub Actions step summary.
"""
from __future__ import annotations

import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://xn--80aafwvmkbibjcl2m.xn--p1ai/"
HOST = urlparse(SITE).hostname
EXCLUDED = {"analytics-consent.html", "googled3be2855f213bfb7.html",
            "yandex_f716343b29761cf2.html"}

class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_count = 0
        self.title_text = []
        self.in_title = False
        self.h1 = 0
        self.description = ""
        self.robots = ""
        self.canonicals = []
        self.links = []
        self.ids = set()
        self.images = []
        self.assets = []
        self.analytics_script = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag in ("img", "video", "audio", "source", "script"):
            for attr in ("src", "poster"):
                if a.get(attr):
                    self.assets.append(a[attr])
        if tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        if tag == "title":
            self.in_title = True
            self.title_count += 1
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta":
            name = (a.get("name") or "").lower()
            if name == "description":
                self.description = a.get("content") or ""
            if name == "robots":
                self.robots = (a.get("content") or "").lower()
        elif tag == "link":
            if "canonical" in (a.get("rel") or "").lower().split():
                self.canonicals.append(a.get("href") or "")
        elif tag == "a":
            href = a.get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_text.append(data)

def local_name(url):
    """Normalize a relative/absolute same-host page URL to root HTML filename."""
    p = urlparse(urljoin(SITE, url))
    if p.hostname != HOST or p.scheme not in ("http", "https"):
        return None
    path = unquote(p.path)
    if path in ("", "/"):
        return "index.html"
    if path.count("/") != 1 or not path.endswith(".html"):
        return None
    return path.lstrip("/")

def main():
    errors = []
    warnings = []
    published = {p.name for p in ROOT.glob("*.html") if p.name not in EXCLUDED}
    try:
        doc = ElementTree.parse(ROOT / "sitemap.xml")
        sitemap = []
        missing_dates = 0
        for url in doc.findall(".//{*}url"):
            loc = url.findtext("{*}loc", "")
            sitemap.append(loc)
            if url.find("{*}lastmod") is None:
                missing_dates += 1
    except (ElementTree.ParseError, OSError) as e:
        print("Sitemap unreadable:", e, file=sys.stderr)
        return 1
    from_sitemap = [local_name(loc) for loc in sitemap]
    for loc, name in zip(sitemap, from_sitemap):
        if name is None or name not in published:
            errors.append("Sitemap points outside published HTML: " + loc)
    for name in sorted(published - set(from_sitemap)):
        errors.append("Published page missing from sitemap: " + name)
    if len(sitemap) != len(set(sitemap)):
        errors.append("Duplicate sitemap URLs")
    if missing_dates:
        warnings.append(str(missing_dates) + " sitemap URLs lack lastmod (do not fabricate modification dates)")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if "Sitemap: " + SITE + "sitemap.xml" not in robots:
        errors.append("robots.txt lacks canonical sitemap URL")
    if "Disallow: /" in robots:
        errors.append("robots.txt blocks all pages")
    scans = {}
    for name in sorted(published):
        page = ROOT / name
        try:
            html = page.read_text(encoding="utf-8")
            p = Scan()
            p.feed(html)
        except (OSError, UnicodeError) as e:
            errors.append(name + ": cannot read HTML: " + str(e))
            continue
        scans[name] = p
        expected = urljoin(SITE, "" if name == "index.html" else name)
        if p.title_count != 1 or not "".join(p.title_text).strip():
            errors.append(name + ": missing/duplicate title")
        if p.h1 != 1:
            errors.append(name + ": expected one H1; found " + str(p.h1))
        if not p.description.strip():
            warnings.append(name + ": missing meta description")
        if "noindex" in p.robots:
            errors.append(name + ": noindex detected")
        if p.canonicals != [expected]:
            errors.append(name + ": non-self canonical: " + repr(p.canonicals))
        if len(html) < 2500:
            warnings.append(name + ": unusually small HTML; inspect substantive content")
        for href in p.links:
            target = local_name(urljoin(expected, href))
            if target and target.endswith(".html") and target not in published and target not in EXCLUDED:
                errors.append(name + ": broken internal HTML link to " + target)
    # Verify anchors against the destination file, not only link filenames.
    # A static link to a nonexistent #fragment renders a clickable but broken
    # service button; a valid target must exist in the HTML at build time.
    for name, page in sorted(scans.items()):
        here = urljoin(SITE, "" if name == "index.html" else name)
        for href in page.links:
            parsed = urlparse(urljoin(here, href))
            if parsed.hostname != HOST or not parsed.fragment:
                continue
            target = local_name(parsed.geturl())
            if not target or target not in scans:
                continue
            fragment = unquote(parsed.fragment)
            if fragment not in scans[target].ids:
                warnings.append(name + ": broken internal section anchor " + href + " (missing #" + fragment + " in " + target + ")")
        for asset in page.assets:
            parsed = urlparse(urljoin(here, asset))
            if parsed.hostname != HOST:
                continue
            if parsed.path.startswith("/assets/"):
                asset_path = ROOT / unquote(parsed.path).lstrip("/")
                if not asset_path.is_file():
                    errors.append(name + ": missing local asset " + asset)

    if "sudebnaya-praktika-i-obraztsy.html" in scans:
        library = scans["sudebnaya-praktika-i-obraztsy.html"]
        listed = {local_name(h) for h in library.links}
        for name in sorted(published - {"index.html", "privacy-policy.html",
                                        "sudebnaya-praktika-i-obraztsy.html",
                                        "zemelnye-spory-yurist-moskva.html"}):
            if name not in listed:
                warnings.append(name + ": no direct link from articles library")
    report = [
        "# ZEUS — технический SEO-аудит",
        "",
        "- Публичных HTML: **" + str(len(published)) + "**",
        "- URL в sitemap.xml: **" + str(len(sitemap)) + "**",
        "- Ошибок: **" + str(len(errors)) + "**",
        "- Предупреждений: **" + str(len(warnings)) + "**",
        "",
        "Проверка исходников **не** подтверждает HTTP 200, реальную публикацию на REG.RU, "
        "индексацию или позиции — для них нужны отдельные внешние проверки.",
    ]
    for label, items in [("Ошибки", errors), ("Предупреждения", warnings)]:
        if items:
            report += ["", "## " + label] + ["- " + item for item in items[:100]]
    output = "\n".join(report) + "\n"
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(output)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
