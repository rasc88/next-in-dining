from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from app.main import app
from app.store import store

from .test_waitlist import join_waitlist

ENV_ATTRIBUTES = {"environment": "local", "version": "dev"}


@pytest.fixture(scope="module")
def reader() -> InMemoryMetricReader:
    # The app's instruments come from the global proxy meter, so installing a
    # provider here routes them into this reader (once per test session).
    reader = InMemoryMetricReader()
    metrics.set_meter_provider(MeterProvider(metric_readers=[reader]))
    return reader


def metric_value(reader: InMemoryMetricReader, name: str, **attributes: str) -> int:
    expected = {**ENV_ATTRIBUTES, **attributes}
    data = reader.get_metrics_data()
    for resource_metrics in data.resource_metrics if data else []:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name != name:
                    continue
                for point in metric.data.data_points:
                    if dict(point.attributes) == expected:
                        return point.value
    return 0


def test_joining_counts_a_created_party(reader: InMemoryMetricReader, client: TestClient) -> None:
    before = metric_value(reader, "waitlist.parties.created")

    join_waitlist(client)

    assert metric_value(reader, "waitlist.parties.created") == before + 1


def test_failed_join_counts_a_creation_failure(
    reader: InMemoryMetricReader, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_create_party(**kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(store, "create_party", broken_create_party)
    before = metric_value(reader, "waitlist.party.creation.failures")

    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/waitlist/join",
        json={"guestName": "Priya Patel", "phoneNumber": "+1-555-0199", "partySize": 3, "seatingCategory": "Indoor"},
    )

    assert response.status_code == 500
    assert metric_value(reader, "waitlist.party.creation.failures") == before + 1


def test_state_changes_count_transitions_by_state(
    reader: InMemoryMetricReader, client: TestClient, host_headers: dict[str, str]
) -> None:
    party_id = join_waitlist(client)["party"]["id"]
    before = metric_value(reader, "waitlist.party.transitions", to_state="NOTIFIED")

    client.patch(f"/v1/waitlist/{party_id}/state", json={"action": "NOTIFY"}, headers=host_headers)

    assert metric_value(reader, "waitlist.party.transitions", to_state="NOTIFIED") == before + 1


def test_guest_cancel_counts_a_cancelled_transition(reader: InMemoryMetricReader, client: TestClient) -> None:
    guest_token = join_waitlist(client)["guestToken"]
    before = metric_value(reader, "waitlist.party.transitions", to_state="CANCELLED")

    client.post("/v1/waitlist/me/cancel", headers={"Authorization": f"Bearer {guest_token}"})

    assert metric_value(reader, "waitlist.party.transitions", to_state="CANCELLED") == before + 1


def test_waiting_gauge_reports_current_queue_length(reader: InMemoryMetricReader, client: TestClient) -> None:
    join_waitlist(client)

    assert metric_value(reader, "waitlist.parties.waiting") == len(store.waiting_parties_ordered())
