from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx
import pytest

COMPOSE_ROOT = Path(__file__).resolve().parents[3]
BASE_URL = "http://localhost:8000"


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)
    except Exception:
        return False
    return True


def _wait_until_up(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            httpx.get(url, timeout=2)
            return
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"{url} never came up within {timeout}s: {last_error}")


@pytest.fixture(scope="session")
def compose_stack() -> str:
    if not _docker_available():
        pytest.skip("Docker is not available (daemon unreachable or permission denied)")

    subprocess.run(["docker", "compose", "up", "--build", "-d"], cwd=COMPOSE_ROOT, check=True)
    try:
        _wait_until_up(f"{BASE_URL}/", timeout=90)
        yield BASE_URL
    finally:
        subprocess.run(["docker", "compose", "down", "-v"], cwd=COMPOSE_ROOT, check=True)


@pytest.fixture()
def psql(compose_stack: str):
    def _query(sql: str) -> str:
        result = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "psql", "-U", "nid", "-d", "nid", "-tAc", sql],
            cwd=COMPOSE_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    return _query
