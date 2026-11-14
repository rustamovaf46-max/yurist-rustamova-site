#!/usr/bin/env python3
"""Read-only Yandex Metrica audit using an existing GitHub Actions OAuth secret."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

COUNTER = 113668938
API = "https://api-metrika.yandex.net"
TOKEN_VAR = "YANDEX_WEBMASTER_TOKEN"  # already authorized with metrika:read
TIMEOUT = 20

def get(path, params=None):
    token = os.environ.get(TOKEN_VAR, "").strip()
    if not token:
        raise RuntimeError("OAuth token missing: use repository Actions secrets")
    query = "?" + urlencode(params) if params else ""
    req = Request(API + path + query, headers={
        "Authorization": "OAuth " + token,
        "Accept": "application/json",
        "User-Agent": "ZEUS-Site-Analytics-Audit/1.0",
    })
    try:
        with urlopen(req, timeout=TIMEOUT) as response:
            return json.load(response)
    except HTTPError as e:
        raise RuntimeError("Yandex Metrica HTTP " + str(e.code) +
                           "; verify OAuth scope and counter access") from None
    except (URLError, TimeoutError) as e:
        raise RuntimeError("Yandex Metrica connection failed: " + str(e)) from None

def main():
    try:
        counter = get("/management/v1/counter/" + str(COUNTER)).get("counter", {})
        if str(counter.get("id")) != str(COUNTER):
            raise RuntimeError("Unexpected Metrica counter ID")
        report = get("/stat/v1/data", {
            "ids": COUNTER,
            "metrics": "ym:s:visits,ym:s:users",
            "date1": "7daysAgo",
            "date2": "yesterday",
            "accuracy": "full",
        })
        totals = report.get("totals", [])
        if len(totals) < 2:
            raise RuntimeError("Yandex did not return visits and users totals")
        goals = get("/management/v1/counter/" + str(COUNTER) + "/goals")
        goal_names = [
            {"id": g.get("id"), "name": g.get("name"), "type": g.get("type")}
            for g in goals.get("goals", [])
        ]
        result = {
            "counter_id": COUNTER,
            "counter_status": counter.get("status"),
            "counter_permission": counter.get("permission"),
            "visits_7d": totals[0],
            "users_7d": totals[1],
            "goals": goal_names,
        }
        output = "## ZEUS — Яндекс Метрика (только чтение)\n\n" + (
            "- Счётчик: **" + str(COUNTER) + "**\n" +
            "- Визиты (7 дней до вчера): **" + str(result["visits_7d"]) + "**\n" +
            "- Посетители: **" + str(result["users_7d"]) + "**\n" +
            "- Целей: **" + str(len(goal_names)) + "**\n\n" +
            "Нажатия на телефон/мессенджер не равны подтвержденным судебным заказам.\n"
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(output)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(output)
        return 0
    except (RuntimeError, ValueError, KeyError) as e:
        print("ERROR:", str(e), file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
