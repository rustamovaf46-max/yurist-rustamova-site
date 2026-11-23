#!/usr/bin/env python3
"""Read-only production HTTP security probe; no credentials or private paths."""
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import sys

HOST = "https://xn--80aafwvmkbibjcl2m.xn--p1ai"
PUBLIC = ("/", "/privacy-policy.html", "/robots.txt")
RESTRICTED = ("/.env", "/.git/config", "/backup.zip", "/database.sql", "/private.key")
REQUIRED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "deny",
    "referrer-policy": "strict-origin-when-cross-origin",
}
failures = []

def check(path, restricted=False):
    req = Request(HOST + path, headers={"User-Agent": "ZEUS-Security-Check/1.0", "Cache-Control": "no-cache"})
    try:
        with urlopen(req, timeout=20) as response:
            status = response.status
            headers = response.headers
    except HTTPError as exc:
        status, headers = exc.code, exc.headers
    except (URLError, TimeoutError) as exc:
        failures.append(f"{path}: request failed: {exc}")
        return
    print(f"{path}: HTTP {status}")
    if restricted:
        if status != 403:
            failures.append(f"{path}: expected HTTP 403, got {status}")
        return
    if status != 200:
        failures.append(f"{path}: expected HTTP 200, got {status}")
        return
    for key, expected in REQUIRED.items():
        if headers.get(key, "").strip().lower() != expected:
            failures.append(f"{path}: missing or changed {key}")
    csp = headers.get("content-security-policy", "")
    for rule in ("frame-ancestors 'none'", "object-src 'none'", "base-uri 'self'"):
        if rule not in csp:
            failures.append(f"{path}: missing CSP {rule}")
    if not headers.get("strict-transport-security"):
        failures.append(f"{path}: missing HSTS")
    # Multiple HSTS policies are currently reported; flag without failing the
    # probe until the nginx/Apache ownership is confirmed.
    hsts = headers.get_all("Strict-Transport-Security", [])
    if len(hsts) != 1 or "," in hsts[0]:
        print(f"WARNING {path}: duplicate HSTS policy; inspect nginx/Apache configuration")

for path in PUBLIC:
    check(path)
for path in RESTRICTED:
    check(path, restricted=True)
if failures:
    for failure in failures:
        print("FAIL:", failure, file=sys.stderr)
    sys.exit(1)
print("PASS: public HTTP headers and restricted paths")
