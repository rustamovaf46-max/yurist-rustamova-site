#!/usr/bin/env python3
"""Execute a narrowly scoped command committed by the owner to the repository.

Only the .github/zeus-yandex-command.json path is read.
The workflow runs on changes to that path. No arbitrary URLs, shell commands,
Yandex site deletion, or DNS operations are accepted.
"""
import json
import sys
from pathlib import Path

import yandex_webmaster as yw

COMMAND_FILE = Path(".github/zeus-yandex-command.json")


def main():
    command = json.loads(COMMAND_FILE.read_text(encoding="utf-8"))
    operation = command.get("operation")
    urls = command.get("urls", [])
    if operation not in ("audit", "verify", "recrawl"):
        raise ValueError("Unsupported command")
    if not isinstance(urls, list) or any(not isinstance(u, str) for u in urls):
        raise ValueError("Invalid list of URLs")
    if operation in ("audit", "verify") and urls:
        raise ValueError("This operation takes no URLs")
    uid, hosts = yw.get_context()
    if operation == "audit":
        return yw.audit(uid, hosts)
    return yw.execute(uid, hosts, operation, urls, confirmed=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, yw.ApiError, OSError) as exc:
        print("ERROR:", str(exc), file=sys.stderr)
        sys.exit(1)
