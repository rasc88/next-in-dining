from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.auth import hash_password, verify_password
from app.models import PartyAction, PartyState, QueueMetrics, WaitlistErrorCode, WaitlistParty

WAITING_HARD_LIMIT = timedelta(hours=12)
RESOLVED_EXPIRY = timedelta(hours=2)

TRANSITIONS: dict[PartyState, dict[PartyAction, PartyState]] = {
    PartyState.WAITING: {PartyAction.NOTIFY: PartyState.NOTIFIED},
    PartyState.NOTIFIED: {
        PartyAction.SEAT: PartyState.SEATED,
        PartyAction.NO_SHOW: PartyState.NO_SHOW,
        PartyAction.RE_NOTIFY: PartyState.NOTIFIED,
    },
    PartyState.SEATED: {PartyAction.UN_SEAT: PartyState.WAITING},
}


class StoreError(Exception):
    def __init__(self, status_code: int, code: WaitlistErrorCode, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class PartyNotFoundError(StoreError):
    def __init__(self, party_id: str):
        super().__init__(404, WaitlistErrorCode.NOT_FOUND, f"No party with id {party_id}.")


class InvalidTransitionError(StoreError):
    def __init__(self, current_state: PartyState, action: str):
        super().__init__(
            409,
            WaitlistErrorCode.INVALID_TRANSITION,
            f'Cannot apply "{action}" to a party in state "{current_state.value}".',
        )


@dataclass
class HostRecord:
    id: str
    email: str
    password_hash: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Store:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.hosts_by_email: dict[str, HostRecord] = {}
        self.host_tokens: dict[str, str] = {}
        self.parties: dict[str, WaitlistParty] = {}
        self.guest_tokens: dict[str, str] = {}
        self.push_subscriptions: dict[str, dict] = {}
        self.peak_hourly_volume: int = 0
        self._seed()

    # -- hosts ---------------------------------------------------------

    def create_host(self, email: str, password: str) -> HostRecord:
        host = HostRecord(id=str(uuid.uuid4()), email=email, password_hash=hash_password(password))
        self.hosts_by_email[email] = host
        return host

    def verify_host_login(self, email: str, password: str) -> HostRecord | None:
        host = self.hosts_by_email.get(email)
        if host is None or not verify_password(password, host.password_hash):
            return None
        return host

    def create_host_token(self, host_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.host_tokens[token] = host_id
        return token

    def revoke_host_token(self, token: str) -> None:
        self.host_tokens.pop(token, None)

    def get_host_by_token(self, token: str) -> HostRecord | None:
        host_id = self.host_tokens.get(token)
        if host_id is None:
            return None
        return next((h for h in self.hosts_by_email.values() if h.id == host_id), None)

    # -- parties ---------------------------------------------------------

    def create_party(
        self,
        guest_name: str,
        phone_number: str,
        party_size: int,
        seating_category: str,
        notes: str | None,
    ) -> tuple[WaitlistParty, str]:
        party = WaitlistParty(
            id=str(uuid.uuid4()),
            guest_name=guest_name,
            phone_number=phone_number,
            party_size=party_size,
            seating_category=seating_category,
            notes=notes,
            state=PartyState.WAITING,
            created_at=_now(),
        )
        self.parties[party.id] = party
        guest_token = secrets.token_urlsafe(32)
        self.guest_tokens[guest_token] = party.id
        self._update_peak()
        return party, guest_token

    def list_active_parties(self) -> list[WaitlistParty]:
        return sorted(self.parties.values(), key=lambda p: p.created_at)

    def get_party(self, party_id: str) -> WaitlistParty | None:
        return self.parties.get(party_id)

    def _is_guest_token_expired(self, party: WaitlistParty) -> bool:
        now = _now()
        if party.state == PartyState.WAITING:
            return now - party.created_at > WAITING_HARD_LIMIT
        if party.resolved_at is not None:
            return now - party.resolved_at > RESOLVED_EXPIRY
        return False

    def get_party_by_guest_token(self, token: str) -> WaitlistParty | None:
        party_id = self.guest_tokens.get(token)
        if party_id is None:
            return None
        party = self.parties.get(party_id)
        if party is None or self._is_guest_token_expired(party):
            return None
        return party

    def waiting_parties_ordered(self) -> list[WaitlistParty]:
        return sorted(
            (p for p in self.parties.values() if p.state == PartyState.WAITING),
            key=lambda p: p.created_at,
        )

    def position_of(self, party_id: str) -> int | None:
        party = self.parties.get(party_id)
        if party is None or party.state != PartyState.WAITING:
            return None
        for index, p in enumerate(self.waiting_parties_ordered()):
            if p.id == party_id:
                return index + 1
        return None

    def update_party_state(self, party_id: str, action: PartyAction) -> WaitlistParty:
        party = self.parties.get(party_id)
        if party is None:
            raise PartyNotFoundError(party_id)
        allowed = TRANSITIONS.get(party.state, {})
        new_state = allowed.get(action)
        if new_state is None:
            raise InvalidTransitionError(party.state, action.value)

        now = _now()
        updates: dict = {"state": new_state}
        if action in (PartyAction.NOTIFY, PartyAction.RE_NOTIFY):
            updates["notified_at"] = now
        if new_state in (PartyState.SEATED, PartyState.NO_SHOW):
            updates["resolved_at"] = now
        if action == PartyAction.UN_SEAT:
            updates["resolved_at"] = None

        party = party.model_copy(update=updates)
        self.parties[party_id] = party
        self._update_peak()
        return party

    def cancel_party(self, party_id: str) -> WaitlistParty:
        party = self.parties.get(party_id)
        if party is None:
            raise PartyNotFoundError(party_id)
        if party.state not in (PartyState.WAITING, PartyState.NOTIFIED):
            raise InvalidTransitionError(party.state, "CANCEL")
        party = party.model_copy(update={"state": PartyState.CANCELLED, "resolved_at": _now()})
        self.parties[party_id] = party
        self._update_peak()
        return party

    def save_push_subscription(self, party_id: str, subscription: dict) -> None:
        self.push_subscriptions[party_id] = subscription
        party = self.parties[party_id]
        self.parties[party_id] = party.model_copy(update={"push_subscribed": True})

    # -- metrics ---------------------------------------------------------

    def _update_peak(self) -> None:
        active_waiting = sum(1 for p in self.parties.values() if p.state == PartyState.WAITING)
        self.peak_hourly_volume = max(self.peak_hourly_volume, active_waiting)

    def metrics(self) -> QueueMetrics:
        active_waiting = sum(1 for p in self.parties.values() if p.state == PartyState.WAITING)
        return QueueMetrics(active_waiting=active_waiting, peak_hourly_volume=self.peak_hourly_volume)

    # -- seed data ---------------------------------------------------------

    def _seed(self) -> None:
        self.create_host("host@waitlist.test", "host1234")

        now = _now()

        def seeded(
            guest_name: str,
            phone_number: str,
            party_size: int,
            seating_category: str,
            state: PartyState,
            created_minutes_ago: int,
            notified_minutes_ago: int | None = None,
            resolved_minutes_ago: int | None = None,
            notes: str | None = None,
        ) -> None:
            party = WaitlistParty(
                id=str(uuid.uuid4()),
                guest_name=guest_name,
                phone_number=phone_number,
                party_size=party_size,
                seating_category=seating_category,
                notes=notes,
                state=state,
                created_at=now - timedelta(minutes=created_minutes_ago),
                notified_at=now - timedelta(minutes=notified_minutes_ago) if notified_minutes_ago is not None else None,
                resolved_at=now - timedelta(minutes=resolved_minutes_ago) if resolved_minutes_ago is not None else None,
            )
            self.parties[party.id] = party
            self.guest_tokens[secrets.token_urlsafe(32)] = party.id

        seeded("Maria Lopez", "+1-555-0101", 2, "Indoor", PartyState.WAITING, created_minutes_ago=18)
        seeded("James Carter", "+1-555-0102", 4, "Outdoor", PartyState.WAITING, created_minutes_ago=12)
        seeded(
            "Wei Chen",
            "+1-555-0103",
            3,
            "Bar",
            PartyState.NOTIFIED,
            created_minutes_ago=25,
            notified_minutes_ago=2,
        )
        seeded(
            "Sofia Rossi",
            "+1-555-0104",
            5,
            "High-top",
            PartyState.SEATED,
            created_minutes_ago=40,
            notified_minutes_ago=15,
            resolved_minutes_ago=10,
        )
        seeded("Ana Silva", "+1-555-0105", 2, "Indoor", PartyState.WAITING, created_minutes_ago=5, notes="Birthday")

        self._update_peak()


store = Store()
