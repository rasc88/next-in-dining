from __future__ import annotations

import os

# Must be set before anything imports app.db, which reads DATABASE_URL at
# import time. Keeps tests off the dev database file.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store


@pytest.fixture()
def client() -> TestClient:
    store.reset()
    return TestClient(app)


@pytest.fixture()
def host_token(client: TestClient) -> str:
    response = client.post("/v1/auth/login", json={"email": "host@waitlist.test", "password": "host1234"})
    return response.json()["token"]


@pytest.fixture()
def host_headers(host_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {host_token}"}
