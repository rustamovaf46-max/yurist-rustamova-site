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
        # Query actual aggregated goal reaches, not merely the list of configured goals.
        # A reach is a website action, never proof of a completed call or signed contract.
        goal_reaches = None
        goal_reaches_error = None
        metric_goals = [
            goal for goal in goal_names
            if isinstance(goal.get("id"), int) and goal["id"] > 0
        ][:18]  # Yandex Reports API allows at most 20 metrics per request.
        if metric_goals:
            try:
                conversions = get("/stat/v1/data", {
                    "ids": COUNTER,
                    "metrics": ",".join(
                        "ym:s:goal" + str(goal["id"]) + "reaches"
                        for goal in metric_goals
                    ),
                    "date1": "7daysAgo",
                    "date2": "yesterday",
                    "accuracy": "full",
                })
                values = conversions.get("totals", [])
                if len(values) != len(metric_goals):
                    raise RuntimeError("Missing conversion totals in Yandex response")
                goal_reaches = [
                    {"id": goal["id"], "name": goal["name"], "reaches_7d": value}
                    for goal, value in zip(metric_goals, values)
                ]
            except (RuntimeError, ValueError, TypeError) as exc:
                goal_reaches_error = str(exc)
        result = {
            "counter_id": COUNTER,
            "counter_status": counter.get("status"),
            "counter_permission": counter.get("permission"),
            "visits_7d": totals[0],
            "users_7d": totals[1],
            "goals": goal_names,
            "goal_reaches_7d": goal_reaches,
            "goal_reaches_error": goal_reaches_error,
        }
        output = "## ZEUS — Яндекс Метрика (только чтение)\n\n" + (
            "- Счётчик: **" + str(COUNTER) + "**\n" +
            "- Визиты (7 дней до вчера): **" + str(result["visits_7d"]) + "**\n" +
            "- Посетители: **" + str(result["users_7d"]) + "**\n" +
            "- Целей: **" + str(len(goal_names)) + "**\n\n" +
            "Нажатия на телефон/мессенджер не равны подтвержденным судебным заказам.\n"
        )
        if goal_reaches is not None:
            output += "\n**Достижения целей за 7 дней (не подтверждённые заявки):**\n"
            for goal in goal_reaches:
                output += "- " + str(goal["name"]) + ": **" + str(goal["reaches_7d"]) + "**\n"
        else:
            output += "\nДостижения целей: **нет достоверных данных**; " + (
                goal_reaches_error or "запрос не выполнен"
            ) + "\n"
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
