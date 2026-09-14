from __future__ import annotations

from fastapi.testclient import TestClient


def join_waitlist(client: TestClient, **overrides) -> dict:
    payload = {
        "guestName": "Priya Patel",
        "phoneNumber": "+1-555-0199",
        "partySize": 3,
        "seatingCategory": "Indoor",
    }
    payload.update(overrides)
    response = client.post("/v1/waitlist/join", json=payload)
    assert response.status_code == 201
    return response.json()


def test_join_waitlist_creates_a_waiting_party(client: TestClient) -> None:
    body = join_waitlist(client)

    assert body["party"]["state"] == "WAITING"
    assert body["party"]["guestName"] == "Priya Patel"
    assert body["guestToken"]


def test_join_waitlist_rejects_invalid_party_size(client: TestClient) -> None:
    response = client.post(
        "/v1/waitlist/join",
        json={
            "guestName": "Priya Patel",
            "phoneNumber": "+1-555-0199",
            "partySize": 0,
            "seatingCategory": "Indoor",
        },
    )

    assert response.status_code == 422


def test_active_queue_includes_seeded_and_new_parties(client: TestClient, host_headers: dict[str, str]) -> None:
    join_waitlist(client)

    response = client.get("/v1/waitlist/active", headers=host_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["parties"]) == 6
    assert body["metrics"]["activeWaiting"] == 4


def test_full_happy_path_state_transitions(client: TestClient, host_headers: dict[str, str]) -> None:
    party_id = join_waitlist(client)["party"]["id"]

    notified = client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "NOTIFY"}, headers=host_headers)
    assert notified.status_code == 200
    assert notified.json()["state"] == "NOTIFIED"
    assert notified.json()["notifiedAt"] is not None

    seated = client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "SEAT"}, headers=host_headers)
    assert seated.status_code == 200
    assert seated.json()["state"] == "SEATED"
    assert seated.json()["resolvedAt"] is not None

    un_seated = client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "UN_SEAT"}, headers=host_headers)
    assert un_seated.status_code == 200
    assert un_seated.json()["state"] == "WAITING"
    assert un_seated.json()["resolvedAt"] is None


def test_invalid_transition_returns_409(client: TestClient, host_headers: dict[str, str]) -> None:
    party_id = join_waitlist(client)["party"]["id"]

    response = client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "SEAT"}, headers=host_headers)

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_state_update_on_unknown_party_returns_404(client: TestClient, host_headers: dict[str, str]) -> None:
    response = client.patch(
        "/v1/waitlist/00000000-0000-0000-0000-000000000000/state",
        json={"action": "NOTIFY"},
        headers=host_headers,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_state_update_requires_host_auth(client: TestClient) -> None:
    party_id = join_waitlist(client)["party"]["id"]

    response = client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "NOTIFY"})

    assert response.status_code == 401


def test_guest_can_read_own_status_and_position(client: TestClient) -> None:
    guest_token = join_waitlist(client)["guestToken"]

    response = client.get("/v1/waitlist/me", headers={"Authorization": f"Bearer {guest_token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["position"] == 4
    assert body["totalWaiting"] == 4


def test_guest_me_rejects_unknown_token(client: TestClient) -> None:
    response = client.get("/v1/waitlist/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


def test_guest_can_cancel_while_waiting(client: TestClient) -> None:
    guest_token = join_waitlist(client)["guestToken"]

    response = client.post("/v1/waitlist/me/cancel", headers={"Authorization": f"Bearer {guest_token}"})

    assert response.status_code == 200
    assert response.json()["state"] == "CANCELLED"


def test_guest_cannot_cancel_once_seated(client: TestClient, host_headers: dict[str, str]) -> None:
    join_result = join_waitlist(client)
    guest_token = join_result["guestToken"]
    party_id = join_result["party"]["id"]
    client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "NOTIFY"}, headers=host_headers)
    client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "SEAT"}, headers=host_headers)

    response = client.post("/v1/waitlist/me/cancel", headers={"Authorization": f"Bearer {guest_token}"})

    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_guest_can_register_push_subscription(client: TestClient) -> None:
    guest_token = join_waitlist(client)["guestToken"]

    response = client.post(
        "/v1/waitlist/me/push-subscribe",
        headers={"Authorization": f"Bearer {guest_token}"},
        json={
            "endpoint": "https://push.example.com/abc123",
            "keys": {"p256dh": "test-p256dh", "auth": "test-auth"},
        },
    )

    assert response.status_code == 204

    status_response = client.get("/v1/waitlist/me", headers={"Authorization": f"Bearer {guest_token}"})
    assert status_response.json()["pushSubscribed"] is True
