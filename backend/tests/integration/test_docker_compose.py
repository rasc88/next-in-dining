from __future__ import annotations

import uuid

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_stack_comes_up_and_seeds_the_demo_host(compose_stack: str) -> None:
    response = httpx.post(
        f"{compose_stack}/v1/auth/login",
        json={"email": "host@waitlist.test", "password": "host1234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["host"]["email"] == "host@waitlist.test"
    assert body["token"]


def test_backend_persists_waitlist_parties_to_postgres(compose_stack: str, psql) -> None:
    guest_name = f"Integration Test {uuid.uuid4().hex[:8]}"
    response = httpx.post(
        f"{compose_stack}/v1/waitlist/join",
        json={
            "guestName": guest_name,
            "phoneNumber": "555-0100",
            "partySize": 2,
            "seatingCategory": "any",
        },
    )
    assert response.status_code == 201
    party_id = response.json()["party"]["id"]

    row = psql(f"select guest_name from waitlist_parties where id = '{party_id}'")
    assert row == guest_name


def test_backend_serves_frontend_with_spa_fallback(compose_stack: str) -> None:
    index = httpx.get(f"{compose_stack}/")
    assert index.status_code == 200
    assert "text/html" in index.headers["content-type"]

    deep_link = httpx.get(f"{compose_stack}/status/some-guest-token")
    assert deep_link.status_code == 200
    assert deep_link.text == index.text


def test_unmatched_api_route_stays_a_json_404(compose_stack: str) -> None:
    response = httpx.get(f"{compose_stack}/v1/does-not-exist")
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]
