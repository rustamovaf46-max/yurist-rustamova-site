#!/usr/bin/env python3
"""Yandex Webmaster API control for the owner's HTTPS website."""
import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

API = "https://api.webmaster.yandex.net/v4"
SITE = "https://xn--80aafwvmkbibjcl2m.xn--p1ai/"
HOST = urlparse(SITE).hostname
TIMEOUT = 20

class ApiError(RuntimeError):
    pass

def request(method, path, data=None):
    token = os.environ.get("YANDEX_WEBMASTER_TOKEN", "").strip()
    if not token:
        raise ApiError("YANDEX_WEBMASTER_TOKEN is not configured in GitHub Actions secrets")
    url = API + path
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = Request(url, method=method, data=body, headers={
        "Authorization": "OAuth " + token,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Zeus-Site-Monitor/1.0",
    })
    # Яндекс периодически отвечает 429/5xx даже при подтверждённом доступе.
    # Повторяем только временные ошибки, никогда — 400/401/403.
    for attempt in range(3):
        try:
            with urlopen(req, timeout=TIMEOUT) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content) if content else {}
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                print(f"Yandex Webmaster HTTP {exc.code}: retry {attempt + 1}/2", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue
            try:
                error_body = json.loads(exc.read().decode("utf-8"))
                reason = error_body.get("error_code") or error_body.get("error_message") or str(exc.code)
            except (ValueError, UnicodeDecodeError):
                reason = str(exc.code)
            raise ApiError(f"Yandex Webmaster HTTP {exc.code}: {reason}") from None
        except (URLError, TimeoutError) as exc:
            if attempt < 2:
                print(f"Yandex Webmaster temporary network failure: retry {attempt + 1}/2", file=sys.stderr)
                time.sleep(2 ** attempt)
                continue
            raise ApiError(f"Yandex Webmaster network error: {exc}") from None
    raise ApiError("Yandex Webmaster retries exhausted")

def get_context():
    identity = request("GET", "/user")
    user_id = identity.get("user_id")
    if user_id is None:
        raise ApiError("Yandex did not provide user_id")
    hosts = request("GET", f"/user/{user_id}/hosts").get("hosts", [])
    return user_id, hosts

def site_host(entry):
    parsed = urlparse(entry.get("ascii_host_url", ""))
    return parsed.hostname == HOST and parsed.scheme in ("http", "https")

def select_https(hosts):
    matching = [host for host in hosts if site_host(host) and
                urlparse(host["ascii_host_url"]).scheme == "https"]
    if len(matching) != 1:
        raise ApiError(f"Expected one HTTPS property; found {len(matching)}. No changes made.")
    return matching[0]

def endpoint(uid, host_id, suffix):
    return f"/user/{uid}/hosts/{quote(host_id, safe='')}/{suffix}"

def audit(uid, hosts):
    matches = [h for h in hosts if site_host(h)]
    print("Yandex Webmaster: site properties (no credentials disclosed)")
    if not matches:
        print("NO_MATCHING_HOST: check owner Yandex ID, OAuth permissions, and site list")
        return 1
    for host in matches:
        host_id = host.get("host_id")
        info = {"url": host.get("ascii_host_url"),
                "verified": host.get("verified"),
                "main_mirror": (host.get("main_mirror") or {}).get("ascii_host_url")}
        if host_id:
            try:
                result = request("GET", endpoint(uid, host_id, "verification"))
                info["verification_state"] = result.get("verification_state")
                info["verification_type"] = result.get("verification_type")
                info["failure_reason"] = (result.get("fail_info") or {}).get("reason")
            except ApiError as exc:
                info["verification_error"] = str(exc)
        if (host_id and host.get("verified") and
                urlparse(host.get("ascii_host_url", "")).scheme == "https"):
            try:
                queue = request("GET", endpoint(uid, host_id, "recrawl/queue?limit=20"))
                tasks = queue.get("tasks", [])
                info["recent_recrawl_tasks"] = [
                    {"url": task.get("url"), "state": task.get("state"),
                     "added_time": task.get("added_time"), "task_id": task.get("task_id")}
                    for task in tasks if urlparse(task.get("url", "")).hostname == HOST
                ][:10]
            except ApiError as exc:
                info["recrawl_queue_error"] = str(exc)
        print(json.dumps(info, ensure_ascii=False))
    return 0 if any(h.get("verified") and urlparse(h.get("ascii_host_url", "")).scheme == "https" for h in matches) else 2

def execute(uid, hosts, operation, urls, confirmed):
    host = select_https(hosts)
    if operation == "verify":
        if host.get("verified"):
            print("HTTPS property already verified.")
            return 0
        path = endpoint(uid, host["host_id"], "verification")
        verification = request("GET", path)
        code = verification.get("verification_uin")
        if not code:
            raise ApiError("No verification code returned")
        proof_url = SITE + "yandex_" + code + ".html"
        try:
            with urlopen(proof_url, timeout=TIMEOUT) as resp:
                text = resp.read(8192).decode("utf-8", errors="replace")
                final_url = resp.geturl()
            if (urlparse(final_url).hostname != HOST or
                    "Verification: " + code not in text):
                raise ApiError("HTTPS verification file absent or mismatched; no write")
        except (HTTPError, URLError) as exc:
            raise ApiError(f"HTTPS verification file unavailable: {exc}") from None
        print("HTTPS proof file confirmed")
        if not confirmed:
            print("DRY RUN; pass --execute for verification write")
            return 0
        result = request("POST", path + "?verification_type=HTML_FILE")
        print("Verification submitted:", result.get("verification_state", "unknown"))
        return 0
    if operation == "recrawl":
        if not host.get("verified"):
            raise ApiError("HTTPS property not verified; refusing recrawl")
        if not urls or len(urls) > 10:
            raise ApiError("Supply between 1 and 10 URLs")
        for url in urls:
            parsed = urlparse(url)
            if (parsed.scheme != "https" or parsed.hostname != HOST or
                    parsed.username or parsed.password or parsed.port):
                raise ApiError("Only canonical HTTPS URLs of the owner's site are accepted")
        if not confirmed:
            print("DRY RUN:", len(urls), "URLs")
            return 0
        path = endpoint(uid, host["host_id"], "recrawl/queue")
        for url in dict.fromkeys(urls):
            outcome = request("POST", path, {"url": url})
            print("Recrawl request:", url, "task:", outcome.get("task_id", "unknown"))
        return 0
    raise ApiError("Unknown operation")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("audit", "verify", "recrawl"))
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        uid, hosts = get_context()
        if args.operation == "audit":
            return audit(uid, hosts)
        return execute(uid, hosts, args.operation, args.url, args.execute)
    except ApiError as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
