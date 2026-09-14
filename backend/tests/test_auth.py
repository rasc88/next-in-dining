from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_succeeds_with_seeded_host(client: TestClient) -> None:
    response = client.post("/v1/auth/login", json={"email": "host@waitlist.test", "password": "host1234"})

    assert response.status_code == 200
    body = response.json()
    assert body["host"]["email"] == "host@waitlist.test"
    assert body["token"]

    protected = client.get("/v1/waitlist/active", headers={"Authorization": f"Bearer {body['token']}"})
    assert protected.status_code == 200


def test_login_fails_with_wrong_password(client: TestClient) -> None:
    response = client.post("/v1/auth/login", json={"email": "host@waitlist.test", "password": "wrong"})

    assert response.status_code == 401
    assert response.json() == {"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password."}


def test_login_fails_with_unknown_email(client: TestClient) -> None:
    response = client.post("/v1/auth/login", json={"email": "nobody@waitlist.test", "password": "host1234"})

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_protected_endpoint_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/v1/waitlist/active")

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


def test_protected_endpoint_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/v1/waitlist/active", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_logout_invalidates_the_token(client: TestClient, host_headers: dict[str, str]) -> None:
    logout_response = client.post("/v1/auth/logout", headers=host_headers)
    assert logout_response.status_code == 204

    reused_response = client.get("/v1/waitlist/active", headers=host_headers)
    assert reused_response.status_code == 401
