#!/usr/bin/env python3
"""Axe-core browser WCAG 2.2 smoke audit for representative public static pages.

Runs against repository file:// copies, never against client data or live analytics.
Automated checks detect only a subset of WCAG success criteria; manual AT/keyboard
review remains necessary. Findings are emitted to JSON and Actions summary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "node_modules" / "axe-core" / "axe.min.js"
REPORTS = ROOT / "reports"
PAGES = [
    "index.html",
    "o-yuriste-fatima-rustamova.html",
    "privacy-policy.html",
    "analytics-consent.html",
    "sudebnaya-praktika-i-obraztsy.html",
    "predstavitelstvo-v-sude-moskva.html",
    "semeynye-spory-yurist-moskva.html",
    "zemelnye-spory-yurist-moskva.html",
    "reforma-gpk-apk-2026-sudebnye-rashody.html",
    "en/reforma-gpk-apk-2026-sudebnye-rashody.html",
    "zh/reforma-gpk-apk-2026-sudebnye-rashody.html",
    "ar/reforma-gpk-apk-2026-sudebnye-rashody.html",
]
TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


def main() -> int:
    if not AXE.is_file():
        raise SystemExit("Install the pinned npm axe-core dependency before auditing.")
    REPORTS.mkdir(exist_ok=True)
    findings = []
    serious = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        for filename in PAGES:
            local = ROOT / filename
            if not local.is_file():
                raise SystemExit("Audit page missing: " + filename)
            for width in (390, 1366):
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.goto(local.as_uri(), wait_until="load", timeout=30000)
                page.add_script_tag(path=str(AXE))
                result = page.evaluate("""async tags => {
                    const a = await axe.run(document, {runOnly: {type:'tag', values:tags}});
                    return {
                      violations:a.violations.map(v => ({
                        id:v.id, impact:v.impact, description:v.description,
                        help:v.help, helpUrl:v.helpUrl,
                        nodes:v.nodes.map(n => ({target:n.target, failureSummary:n.failureSummary}))
                      })),
                      incomplete:a.incomplete.map(v=>({id:v.id,impact:v.impact,count:v.nodes.length})),
                      passCount:a.passes.length
                    };
                }""", TAGS)
                for v in result["violations"]:
                    if v["impact"] in ("serious", "critical"):
                        serious += 1
                findings.append({"page": filename, "viewport": width, **result})
                print(f"WCAG axe: {filename} {width}px; violations={len(result['violations'])}; "
                      f"needs_review={len(result['incomplete'])}; passed_rules={result['passCount']}", flush=True)
                page.close()
        browser.close()
    output = REPORTS / "zeus-wcag22-browser-audit.json"
    output.write_text(json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [
        "## Automated WCAG 2.2 A/AA browser audit (not a conformance certificate)",
        f"Scanned {len(findings)} page/viewport combinations. "
        f"Serious/critical violations: {serious}.",
        "| Page | px | Violations | Requires manual review |",
        "|---|---:|---:|---:|",
    ]
    for item in findings:
        rows.append(f"| `{item['page']}` | {item['viewport']} | "
                    f"{len(item['violations'])} | {len(item['incomplete'])} |")
    rows.append("")
    rows.append("Axe cannot test every WCAG criterion. Manual keyboard, screen reader, "
                "contrast at varying text sizes and legal translation review remain required.")
    summary = "\n".join(rows) + "\n"
    (REPORTS / "zeus-wcag22-browser-audit.md").write_text(summary, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(summary)
    if serious:
        print(f"::error::{serious} serious or critical accessibility violations; see report.")
    return 1 if serious else 0


if __name__ == "__main__":
    raise SystemExit(main())
