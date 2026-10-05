"""On-call engineer: polls Grafana for firing alerts and hands each new
incident to a headless Claude Code session that investigates and fixes it.

A proof of concept that runs on a developer machine (stdlib only):

    export GRAFANA_URL=https://<stack>.grafana.net
    export GRAFANA_TOKEN=<service account token with the Viewer role>
    python3 on-call-engineer/oncall.py          # poll every 60s
    python3 on-call-engineer/oncall.py --once   # single poll, for testing

GRAFANA_TOKEN can be omitted for the local Grafana (anonymous access).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parent
PROMPT_FILE = HERE / "prompt.md"
STATE_FILE = HERE / "state.json"
LOG_DIR = HERE / "logs"

SERVICE = "next-in-dining"
GRAFANA_URL = os.environ["GRAFANA_URL"].rstrip("/")
GRAFANA_TOKEN = os.environ.get("GRAFANA_TOKEN")
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
AGENT_TIMEOUT_SECONDS = 30 * 60

# Enough to read the code, edit it, run the backend tests and commit -
# but not to push, deploy or touch anything outside the repo.
ALLOWED_TOOLS = [
    "Read",
    "Grep",
    "Glob",
    "Edit",
    "Write",
    "Bash(make -C backend test)",
    "Bash(make -C backend install)",
    "Bash(backend/.venv/bin/pytest:*)",
    "Bash(git status)",
    "Bash(git log:*)",
    "Bash(git show:*)",
    "Bash(git diff:*)",
    "Bash(git add:*)",
    "Bash(git commit:*)",
]


def fetch_firing_alerts() -> list[dict]:
    headers = {"Authorization": f"Bearer {GRAFANA_TOKEN}"} if GRAFANA_TOKEN else {}
    request = urllib.request.Request(f"{GRAFANA_URL}/api/prometheus/grafana/api/v1/alerts", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        alerts = json.load(response)["data"]["alerts"]
    # Grafana reports a firing alert as "Alerting" (or "Alerting (NoData)" /
    # "Alerting (Error)"); "Pending" hasn't lasted its `for` duration yet.
    return [a for a in alerts if a["state"].startswith("Alerting") and a["labels"].get("service") == SERVICE]


def incident_key(alert: dict) -> str:
    # activeAt changes each time the alert fires anew, so a resolved-then-
    # refired alert is a new incident, while one that keeps firing isn't.
    labels = alert["labels"]
    return "|".join([labels["alertname"], labels.get("environment", ""), labels.get("version", ""), alert["activeAt"]])


def load_handled() -> set[str]:
    return set(json.loads(STATE_FILE.read_text())) if STATE_FILE.exists() else set()


def save_handled(handled: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(handled), indent=2))


def run_agent(alert: dict) -> Path:
    prompt = f"{PROMPT_FILE.read_text()}\n## Alert\n\n```json\n{json.dumps(alert, indent=2)}\n```\n"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{timestamp}-{alert['labels'].get('environment', 'unknown')}.log"
    with log_file.open("w") as log:
        log.write(f"# Alert\n{json.dumps(alert, indent=2)}\n\n# Agent session\n")
        log.flush()
        subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--allowedTools", *ALLOWED_TOOLS],
            cwd=REPO_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=AGENT_TIMEOUT_SECONDS,
            check=False,
        )
    return log_file


def poll_once(handled: set[str]) -> None:
    for alert in fetch_firing_alerts():
        key = incident_key(alert)
        if key in handled:
            continue
        print(f"{datetime.now():%H:%M:%S} Firing: {alert['annotations'].get('summary', key)} - starting agent", flush=True)
        # Mark it before running, so a crash mid-session doesn't relaunch an
        # agent on the same incident in a loop.
        handled.add(key)
        save_handled(handled)
        log_file = run_agent(alert)
        print(f"{datetime.now():%H:%M:%S} Agent finished, session log: {log_file}", flush=True)


def main() -> None:
    handled = load_handled()
    print(f"Watching {GRAFANA_URL} for firing '{SERVICE}' alerts every {POLL_SECONDS}s", flush=True)
    while True:
        try:
            poll_once(handled)
        except Exception as exc:  # keep the watcher alive through network blips
            print(f"{datetime.now():%H:%M:%S} Poll failed: {exc}", file=sys.stderr, flush=True)
        if "--once" in sys.argv:
            return
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
