#!/usr/bin/env python3
"""Read-only Gemini and Alice SEO reviews of PUBLIC repo pages. All API calls opt-in.

No source/site mutations. No client documents. Never logs tokens or API keys.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    "index.html",
    "predstavitelstvo-v-sude-moskva.html",
    "zemelnye-spory-yurist-moskva.html",
    "semeynye-spory-yurist-moskva.html",
    "nasledstvennye-spory-yurist-moskva.html",
    "zhilishchnye-spory-yurist-moskva.html",
    "arbitrazhnye-spory-yurist-moskva.html",
    "pensionnye-spory-sfr-sud-moskva.html",
    "voennye-spory-vyplaty-semyam-moskva.html",
    "sudebnyy-yurist-goroda-moskovskoy-oblasti.html",
    "sudebnyy-yurist-moskva-stantsii-metro.html",
]
SYSTEM = (
    "Ты независимый технический SEO-аналитик русскоязычного юридического сайта. "
    "Критически оцени только предоставленный публичный HTML. "
    "Не утверждай, что посетил живой сайт, получил доступ к поисковой выдаче, "
    "Google Search Console или Яндекс Вебмастеру, если это не так. "
    "Разделяй проверенные факты и гипотезы, выделяй риск дорвеев, "
    "качество юридических материалов, тематическую перелинковку, структуру услуг, "
    "доступность и оригинальность. Найди максимум десять приоритетных исправлений "
    "с точными ссылками и объяснениями. Не гарантируй индексацию и лиды. "
    "Запрещено цитировать или домысливать закрытые дела и персональные данные клиентов."
)

class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignored = 0
        self.text = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.ignored += 1
        if tag == "a" and props.get("href"):
            self.links.append(props["href"])
    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.ignored:
            self.ignored -= 1
    def handle_data(self, data):
        if not self.ignored and data.strip():
            self.text.append(" ".join(data.split()))

def evidence():
    blocks = []
    for name in PAGES:
        raw = (ROOT / name).read_text("utf-8")
        p = Extract()
        p.feed(raw)
        meaningful = " ".join(p.text)[:2300]
        title = re.search(r"<title>([^<]+)</title>", raw, re.I)
        desc = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', raw, re.I)
        internal = sorted({a for a in p.links if a.startswith("/") and a.endswith(".html")})
        blocks.append(json.dumps({
            "page": "https://юриструстамова.рф/" + ("" if name == "index.html" else name),
            "title": title.group(1) if title else "",
            "description": desc.group(1) if desc else "",
            "text_sample": meaningful,
            "internal_links": internal[:30],
        }, ensure_ascii=False))
    return SYSTEM + "\n\nПроверяемые публичные материалы из GitHub, не живой сайт:\n" + "\n".join(blocks)

def post_json(endpoint, headers, data):
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=50) as r:
        return json.load(r)

def review_gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY отсутствует в GitHub Secrets")
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    result = post_json(endpoint, {"x-goog-api-key": key, "Content-Type": "application/json"},
                       {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"maxOutputTokens": 2500}})
    return "\n".join(str(part.get("text", "")) for c in result.get("candidates", []) for part in c.get("content", {}).get("parts", [])).strip()

def review_alice(prompt):
    key, folder = os.environ.get("YANDEX_AI_API_KEY", ""), os.environ.get("YANDEX_AI_FOLDER_ID", "")
    if not key or not folder:
        raise RuntimeError("YANDEX_AI_API_KEY или YANDEX_AI_FOLDER_ID отсутствует в Secrets")
    result = post_json("https://ai.api.cloud.yandex.net/v1/responses",
                       {"Authorization": "Api-Key " + key, "Content-Type": "application/json"},
                       {"model": f"gpt://{folder}/aliceai-llm", "input": prompt,
                        "max_output_tokens": 2200, "temperature": 0.2})
    return "\n".join(str(block.get("text", "")) for item in result.get("output", []) for block in item.get("content", []) if block.get("type") == "output_text").strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=["gemini", "alice", "both", "dry-run"], default="dry-run")
    p.add_argument("--approved", choices=["no", "yes"], default="no")
    args = p.parse_args()
    prompt = evidence()
    print("Проверено исходных публичных страниц:", len(PAGES))
    print("Длина запроса (символов):", len(prompt))
    if args.approved != "yes" or args.provider == "dry-run":
        print("DRY RUN: API Gemini / Alice НЕ ВЫЗВАНЫ, расходов нет.")
        return 0
    models = ["gemini", "alice"] if args.provider == "both" else [args.provider]
    out = Path("zeus-ai-reports")
    out.mkdir(exist_ok=True)
    for name in models:
        try:
            text = (review_gemini if name == "gemini" else review_alice)(prompt)
            if not text:
                raise RuntimeError("Модель вернула пустой ответ")
            (out / (name + ".md")).write_text("# Независимый аудит: " + name + "\n\n" + text, encoding="utf-8")
            print(name, "сформировал отчёт (не равно подтверждению индексации).")
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, RuntimeError) as exc:
            # Avoid full response bodies: they might contain sensitive upstream metadata.
            print(name + ": ошибка подключения: " + type(exc).__name__, file=sys.stderr)
            return 2
    print("Отчёты остались в артефактах CI; сайт и бюджет не изменены.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
