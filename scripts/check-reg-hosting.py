"""Read-only pre-migration checks; never modifies DNS or hosting."""
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

HOST = "xn--80aafwvmkbibjcl2m.xn--p1ai"
IP = "37.140.192.146"
KEY_FILE = "91f7e03d63fefe7098456dca52d83d4a.txt"
GOOGLE_FILE = "googled3be2855f213bfb7.html"
ROOT = pathlib.Path.cwd()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.ids = set()
        self.json_blocks = []
        self.json_open = False
        self.json_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for name in ("href", "src", "poster"):
            if attrs.get(name):
                self.refs.append(attrs[name])
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.json_open = True
            self.json_parts = []

    def handle_data(self, data):
        if self.json_open:
            self.json_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.json_open:
            self.json_blocks.append("".join(self.json_parts))
            self.json_open = False


def source_checks():
    issues = []
    pages = {}
    for path in sorted(ROOT.glob("*.html")):
        if path.name.startswith("google"):
            continue
        parser = PageParser()
        body = path.read_text(encoding="utf-8")
        parser.feed(body)
        pages[path.name] = parser
        if "xn--80aafwvmkbibjcl2m.xn--p1ai" not in body:
            issues.append({"page": path.name, "issue": "canonical_domain_missing"})
        for block in parser.json_blocks:
            try:
                json.loads(block)
            except ValueError as exc:
                issues.append({"page": path.name, "issue": "invalid_json_ld", "error": str(exc)})
        for asset in re.findall(r"assets/[a-zA-Z0-9._/-]+", body):
            if not (ROOT / asset).is_file():
                issues.append({"page": path.name, "issue": "missing_asset", "ref": asset})
    for name, page in pages.items():
        for ref in page.refs:
            parsed = urllib.parse.urlsplit(ref)
            if parsed.scheme or parsed.netloc:
                continue
            path = urllib.parse.unquote(parsed.path)
            target = "index.html" if path in ("/", "./") else path.lstrip("/")
            if not target:
                target = name
            target = str(pathlib.Path(name).parent / target)
            if not (ROOT / target).is_file():
                issues.append({"page": name, "issue": "missing_page_or_file", "ref": ref})
            elif parsed.fragment and target in pages and parsed.fragment not in pages[target].ids:
                issues.append({"page": name, "issue": "missing_anchor", "ref": ref})
    sitemap = ET.parse(ROOT / "sitemap.xml")
    locations = [el.text for el in sitemap.iter() if el.tag.endswith("loc")]
    for location in locations:
        parsed = urllib.parse.urlsplit(location)
        path = parsed.path.lstrip("/") or "index.html"
        if parsed.hostname != HOST or parsed.scheme != "https" or not (ROOT / path).is_file():
            issues.append({"issue": "invalid_sitemap_url", "url": location})
    return {"html_pages": len(pages), "sitemap_urls": locations, "issues": issues}


def request(url, pin_to_reg=False):
    with tempfile.TemporaryDirectory() as tmp:
        payload_path = pathlib.Path(tmp) / "body"
        command = [
            "curl", "--silent", "--show-error", "--location", "--max-redirs", "4",
            "--connect-timeout", "8", "--max-time", "25",
            "--output", str(payload_path), "--write-out", "%{json}",
            "--user-agent", "Rustamova-Hosting-Preflight/1.0",
        ]
        if pin_to_reg:
            for host in (HOST, "www." + HOST):
                for port in (80, 443):
                    command += ["--resolve", f"{host}:{port}:{IP}"]
        command.append(url)
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        try:
            meta = json.loads(result.stdout)
        except ValueError:
            meta = {}
        body = payload_path.read_bytes() if payload_path.exists() else b""
        return {
            "requested_url": url,
            "http_status": meta.get("http_code", 0),
            "content_type": meta.get("content_type"),
            "final_url": meta.get("url_effective"),
            "remote_ip": meta.get("remote_ip"),
            "ssl_verify_result": meta.get("ssl_verify_result"),
            "curl_exit": result.returncode,
            "error": result.stderr.strip()[:400] if result.returncode else None,
            "body": body,
        }


def route_check(route, origin):
    pin = origin == "reg"
    scheme = "http" if pin else "https"
    result = request(f"{scheme}://{HOST}{route}", pin)
    payload = result.pop("body")
    source_path = ROOT / (route.lstrip("/") or "index.html")
    result["bytes"] = len(payload)
    result["matches_repository"] = hashlib.sha256(payload).digest() == hashlib.sha256(source_path.read_bytes()).digest()
    result["ok"] = result["curl_exit"] == 0 and result["http_status"] == 200 and bool(payload)
    if pin:
        result["ok"] = result["ok"] and result["remote_ip"] == IP
    text = payload.decode("utf-8", errors="replace") if route.endswith((".html", ".txt", ".xml")) or route == "/" else ""
    if route == "/":
        flags = {"owner": "Рустамова" in text, "phone": "79099282398" in text, "canonical": "https://" + HOST in text}
        result["content_flags"] = flags
        result["ok"] = result["ok"] and all(flags.values())
    elif route.endswith("/" + GOOGLE_FILE):
        result["ok"] = result["ok"] and text.strip() == "google-site-verification: " + GOOGLE_FILE
    elif route.endswith("/" + KEY_FILE):
        result["ok"] = result["ok"] and text.strip() == pathlib.Path(KEY_FILE).stem
    elif route.endswith(".webp"):
        result["ok"] = result["ok"] and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    elif route.endswith(".mp4"):
        result["ok"] = result["ok"] and payload[4:8] == b"ftyp"
    elif route.endswith(".html"):
        result["ok"] = result["ok"] and ("<html" in text.lower() or "<!doctype" in text.lower())
    elif route.endswith(".xml"):
        try:
            ET.fromstring(payload)
        except ET.ParseError:
            result["ok"] = False
    return route, result


def dns_snapshot():
    queries = [(HOST, kind) for kind in ("A", "AAAA", "NS", "MX", "TXT", "CAA")]
    queries += [("www." + HOST, kind) for kind in ("A", "AAAA", "CNAME")]
    queries += [("_dmarc." + HOST, "TXT")]
    results = {}
    for server in ("ns1.reg.ru", "ns2.reg.ru"):
        records = {}
        for name, kind in queries:
            cmd = ["dig", "+time=3", "+tries=1", "+noall", "+answer", "@" + server, name, kind]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            records[f"{name} {kind}"] = {"answer": out.stdout.strip(), "exit": out.returncode}
        results[server] = records
    return results


def main():
    source = source_checks()
    routes = ["/", "/robots.txt", "/sitemap.xml", "/" + GOOGLE_FILE, "/" + KEY_FILE]
    routes += ["/" + path.name for path in sorted(ROOT.glob("*.html")) if path.name != "index.html" and not path.name.startswith("google")]
    routes += ["/" + str(path.relative_to(ROOT)) for path in sorted((ROOT / "assets").glob("*")) if path.is_file()]
    report = {"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "domain": HOST, "new_ip": IP, "source": source, "origins": {"reg": {}, "public": {}}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        dns_future = pool.submit(dns_snapshot)
        tasks = {pool.submit(route_check, route, origin): (route, origin) for origin in ("reg", "public") for route in routes}
        for future in concurrent.futures.as_completed(tasks):
            route, origin = tasks[future]
            try:
                _, check = future.result()
            except Exception as exc:
                check = {"ok": False, "error": str(exc)}
            report["origins"][origin][route] = check
        report["authoritative_dns"] = dns_future.result()
    report["new_origin_http_ready"] = not source["issues"] and all(check["ok"] for check in report["origins"]["reg"].values())
    report["new_origin_tls"] = {}
    for host in (HOST, "www." + HOST):
        result = request("https://" + host + "/", pin_to_reg=True)
        body = result.pop("body")
        result["has_owner"] = "Рустамова" in body.decode("utf-8", errors="replace")
        result["ok"] = result["curl_exit"] == 0 and result["http_status"] == 200 and result["remote_ip"] == IP and result["has_owner"]
        report["new_origin_tls"][host] = result
    report["limitations"] = ["Filesystem owner and permissions, full DNS zone backup, and browser/mobile layout require hosting access.", "This workflow performs no DNS changes, certificate installation or deployment."]
    output = pathlib.Path(os.environ.get("RUNNER_TEMP", ".")) / "reg-hosting-preflight.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
    if not report["new_origin_http_ready"]:
        raise SystemExit("New origin has not passed HTTP/content checks; do not switch DNS.")


if __name__ == "__main__":
    main()
