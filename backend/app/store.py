from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import db
from app.auth import hash_password, verify_password
from app.db_models import (
    GuestTokenRow,
    HostTokenRow,
    HostUserRow,
    PushSubscriptionRow,
    ShiftMetricsRow,
    WaitlistPartyRow,
)
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


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite round-trips our UTC datetimes as naive; treat naive as UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _party_from_row(row: WaitlistPartyRow) -> WaitlistParty:
    return WaitlistParty(
        id=row.id,
        guest_name=row.guest_name,
        phone_number=row.phone_number,
        party_size=row.party_size,
        seating_category=row.seating_category,
        notes=row.notes,
        state=row.state,
        created_at=_as_utc(row.created_at),
        notified_at=_as_utc(row.notified_at),
        resolved_at=_as_utc(row.resolved_at),
        push_subscribed=row.push_subscribed,
    )


class Store:
    """Thin wrapper over the database: each method opens its own session.

    Nothing here holds request-scoped state, so a plain module-level
    instance (see `store` below) can serve every request the same way the
    original in-memory version did.
    """

    def __init__(self) -> None:
        db.init_db()
        with db.SessionLocal() as session:
            if session.query(HostUserRow).count() == 0:
                self._seed(session)
                session.commit()

    def reset(self) -> None:
        """Drop and recreate every table, then reseed. Used by tests for isolation."""
        db.Base.metadata.drop_all(db.engine)
        db.Base.metadata.create_all(db.engine)
        with db.SessionLocal() as session:
            self._seed(session)
            session.commit()

    # -- hosts ---------------------------------------------------------

    def _insert_host(self, session: Session, email: str, password: str) -> HostUserRow:
        row = HostUserRow(id=str(uuid.uuid4()), email=email, password_hash=hash_password(password))
        session.add(row)
        return row

    def create_host(self, email: str, password: str) -> HostRecord:
        with db.SessionLocal() as session:
            row = self._insert_host(session, email, password)
            session.commit()
            return HostRecord(id=row.id, email=row.email, password_hash=row.password_hash)

    def verify_host_login(self, email: str, password: str) -> HostRecord | None:
        with db.SessionLocal() as session:
            row = session.scalar(select(HostUserRow).where(HostUserRow.email == email))
            if row is None or not verify_password(password, row.password_hash):
                return None
            return HostRecord(id=row.id, email=row.email, password_hash=row.password_hash)

    def create_host_token(self, host_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with db.SessionLocal() as session:
            session.add(HostTokenRow(token=token, host_id=host_id))
            session.commit()
        return token

    def revoke_host_token(self, token: str) -> None:
        with db.SessionLocal() as session:
            row = session.get(HostTokenRow, token)
            if row is not None:
                session.delete(row)
                session.commit()

    def get_host_by_token(self, token: str) -> HostRecord | None:
        with db.SessionLocal() as session:
            token_row = session.get(HostTokenRow, token)
            if token_row is None:
                return None
            host_row = session.get(HostUserRow, token_row.host_id)
            if host_row is None:
                return None
            return HostRecord(id=host_row.id, email=host_row.email, password_hash=host_row.password_hash)

    # -- parties ---------------------------------------------------------

    def create_party(
        self,
        guest_name: str,
        phone_number: str,
        party_size: int,
        seating_category: str,
        notes: str | None,
    ) -> tuple[WaitlistParty, str]:
        with db.SessionLocal() as session:
            row = WaitlistPartyRow(
                id=str(uuid.uuid4()),
                guest_name=guest_name,
                phone_number=phone_number,
                party_size=party_size,
                seating_category=seating_category,
                notes=notes,
                state=PartyState.WAITING,
                created_at=_now(),
            )
            session.add(row)
            session.flush()

            guest_token = secrets.token_urlsafe(32)
            session.add(GuestTokenRow(token=guest_token, party_id=row.id))

            self._update_peak(session)
            session.commit()
            return _party_from_row(row), guest_token

    def list_active_parties(self) -> list[WaitlistParty]:
        with db.SessionLocal() as session:
            rows = session.scalars(select(WaitlistPartyRow).order_by(WaitlistPartyRow.created_at)).all()
            return [_party_from_row(row) for row in rows]

    def get_party(self, party_id: str) -> WaitlistParty | None:
        with db.SessionLocal() as session:
            row = session.get(WaitlistPartyRow, party_id)
            return _party_from_row(row) if row else None

    def _is_guest_token_expired(self, row: WaitlistPartyRow) -> bool:
        now = _now()
        if row.state == PartyState.WAITING:
            return now - _as_utc(row.created_at) > WAITING_HARD_LIMIT
        resolved_at = _as_utc(row.resolved_at)
        if resolved_at is not None:
            return now - resolved_at > RESOLVED_EXPIRY
        return False

    def get_party_by_guest_token(self, token: str) -> WaitlistParty | None:
        with db.SessionLocal() as session:
            token_row = session.get(GuestTokenRow, token)
            if token_row is None:
                return None
            party_row = session.get(WaitlistPartyRow, token_row.party_id)
            if party_row is None or self._is_guest_token_expired(party_row):
                return None
            return _party_from_row(party_row)

    def waiting_parties_ordered(self) -> list[WaitlistParty]:
        with db.SessionLocal() as session:
            rows = session.scalars(
                select(WaitlistPartyRow)
                .where(WaitlistPartyRow.state == PartyState.WAITING)
                .order_by(WaitlistPartyRow.created_at)
            ).all()
            return [_party_from_row(row) for row in rows]

    def position_of(self, party_id: str) -> int | None:
        for index, party in enumerate(self.waiting_parties_ordered()):
            if party.id == party_id:
                return index + 1
        return None

    def update_party_state(self, party_id: str, action: PartyAction) -> WaitlistParty:
        with db.SessionLocal() as session:
            row = session.get(WaitlistPartyRow, party_id)
            if row is None:
                raise PartyNotFoundError(party_id)

            allowed = TRANSITIONS.get(row.state, {})
            new_state = allowed.get(action)
            if new_state is None:
                raise InvalidTransitionError(row.state, action.value)

            now = _now()
            row.state = new_state
            if action in (PartyAction.NOTIFY, PartyAction.RE_NOTIFY):
                row.notified_at = now
            if new_state in (PartyState.SEATED, PartyState.NO_SHOW):
                row.resolved_at = now
            if action == PartyAction.UN_SEAT:
                row.resolved_at = None

            self._update_peak(session)
            session.commit()
            return _party_from_row(row)

    def cancel_party(self, party_id: str) -> WaitlistParty:
        with db.SessionLocal() as session:
            row = session.get(WaitlistPartyRow, party_id)
            if row is None:
                raise PartyNotFoundError(party_id)
            if row.state not in (PartyState.WAITING, PartyState.NOTIFIED):
                raise InvalidTransitionError(row.state, "CANCEL")

            row.state = PartyState.CANCELLED
            row.resolved_at = _now()
            session.commit()
            return _party_from_row(row)

    def save_push_subscription(self, party_id: str, subscription: dict) -> None:
        with db.SessionLocal() as session:
            party_row = session.get(WaitlistPartyRow, party_id)
            if party_row is None:
                raise PartyNotFoundError(party_id)

            existing = session.get(PushSubscriptionRow, party_id)
            if existing is None:
                session.add(PushSubscriptionRow(party_id=party_id, subscription=subscription))
            else:
                existing.subscription = subscription

            party_row.push_subscribed = True
            session.commit()

    # -- metrics ---------------------------------------------------------

    def _count_waiting(self, session: Session) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(WaitlistPartyRow)
                .where(WaitlistPartyRow.state == PartyState.WAITING)
            )
            or 0
        )

    def _update_peak(self, session: Session) -> None:
        active_waiting = self._count_waiting(session)
        metrics_row = session.get(ShiftMetricsRow, 1)
        if metrics_row is None:
            session.add(ShiftMetricsRow(id=1, peak_hourly_volume=active_waiting))
        else:
            metrics_row.peak_hourly_volume = max(metrics_row.peak_hourly_volume, active_waiting)

    def metrics(self) -> QueueMetrics:
        with db.SessionLocal() as session:
            active_waiting = self._count_waiting(session)
            metrics_row = session.get(ShiftMetricsRow, 1)
            peak = metrics_row.peak_hourly_volume if metrics_row is not None else active_waiting
            return QueueMetrics(active_waiting=active_waiting, peak_hourly_volume=peak)

    # -- seed data ---------------------------------------------------------

    def _seed(self, session: Session) -> None:
        self._insert_host(session, "host@waitlist.test", "host1234")

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
            row = WaitlistPartyRow(
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
            session.add(row)
            session.flush()
            session.add(GuestTokenRow(token=secrets.token_urlsafe(32), party_id=row.id))

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

        self._update_peak(session)


store = Store()
