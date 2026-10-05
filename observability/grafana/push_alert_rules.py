"""Push the alert rules in provisioning/alerting/rules.json to a Grafana
instance (e.g. Grafana Cloud) through its alerting provisioning API.

The local Grafana loads rules.json from disk; a hosted Grafana can't, so
this script fills in the two local-only values - the Prometheus datasource
UID and the dashboard base URL - and upserts each rule group.

Usage (stdlib only, no virtualenv needed):

    export GRAFANA_URL=https://<stack>.grafana.net
    export GRAFANA_TOKEN=<service account token with the Editor role>
    python3 observability/grafana/push_alert_rules.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

RULES_FILE = Path(__file__).parent / "provisioning" / "alerting" / "rules.json"
LOCAL_DASHBOARD_BASE_URL = "http://localhost:3000"

GRAFANA_URL = os.environ["GRAFANA_URL"].rstrip("/")
GRAFANA_TOKEN = os.environ["GRAFANA_TOKEN"]


def api(method: str, path: str, body: dict | None = None) -> dict | list:
    request = urllib.request.Request(
        f"{GRAFANA_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {GRAFANA_TOKEN}",
            "Content-Type": "application/json",
            # Keep the rules editable in the Grafana UI.
            "X-Disable-Provenance": "true",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"{}")


def prometheus_datasource_uid() -> str:
    datasources = [ds for ds in api("GET", "/api/datasources") if ds["type"] == "prometheus"]
    # Grafana Cloud's own metrics datasource is named grafanacloud-<stack>-prom.
    for ds in datasources:
        if re.fullmatch(r"grafanacloud-.+-prom", ds["name"]):
            return ds["uid"]
    if not datasources:
        sys.exit("No Prometheus datasource found in this Grafana")
    return datasources[0]["uid"]


def ensure_folder(uid: str, title: str) -> None:
    # Looking an unknown folder up is a 403 (not a 404) for non-admins, so
    # just create it and treat "already exists" as success.
    try:
        api("POST", "/api/folders", {"uid": uid, "title": title})
    except urllib.error.HTTPError as exc:
        if exc.code not in (409, 412):
            raise


def parse_seconds(duration: str) -> int:
    value, unit = int(duration[:-1]), duration[-1]
    return value * {"s": 1, "m": 60, "h": 3600}[unit]


def main() -> None:
    prom_uid = prometheus_datasource_uid()
    rules_json = RULES_FILE.read_text()
    rules_json = rules_json.replace("${PROM_DATASOURCE_UID}", prom_uid)
    rules_json = rules_json.replace(LOCAL_DASHBOARD_BASE_URL, GRAFANA_URL)

    for group in json.loads(rules_json)["groups"]:
        folder_uid = group["folder"]
        ensure_folder(folder_uid, group["folder"])
        rules = [{**rule, "folderUID": folder_uid, "ruleGroup": group["name"]} for rule in group["rules"]]
        api(
            "PUT",
            f"/api/v1/provisioning/folder/{folder_uid}/rule-groups/{group['name']}",
            {"title": group["name"], "folderUid": folder_uid, "interval": parse_seconds(group["interval"]), "rules": rules},
        )
        for rule in rules:
            print(f"Pushed '{rule['title']}' to folder '{folder_uid}' (Prometheus datasource {prom_uid})")


if __name__ == "__main__":
    main()
