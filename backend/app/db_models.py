from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models import PartyState


class Base(DeclarativeBase):
    pass


class HostUserRow(Base):
    __tablename__ = "host_users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)


class HostTokenRow(Base):
    __tablename__ = "host_tokens"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    host_id: Mapped[str] = mapped_column(String, ForeignKey("host_users.id"))


class WaitlistPartyRow(Base):
    __tablename__ = "waitlist_parties"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    guest_name: Mapped[str] = mapped_column(String)
    phone_number: Mapped[str] = mapped_column(String)
    party_size: Mapped[int] = mapped_column(Integer)
    seating_category: Mapped[str] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[PartyState] = mapped_column(SqlEnum(PartyState), default=PartyState.WAITING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    push_subscribed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class GuestTokenRow(Base):
    __tablename__ = "guest_tokens"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    party_id: Mapped[str] = mapped_column(String, ForeignKey("waitlist_parties.id"))


class PushSubscriptionRow(Base):
    __tablename__ = "push_subscriptions"

    party_id: Mapped[str] = mapped_column(String, ForeignKey("waitlist_parties.id"), primary_key=True)
    subscription: Mapped[dict] = mapped_column(JSON)


class ShiftMetricsRow(Base):
    """Single-row table holding the running peak-WAITING-count for the shift.

    Peak isn't derivable from current party states alone (a party that
    contributed to the peak may since have moved on), so it has to be
    persisted as its own counter rather than computed on read.
    """

    __tablename__ = "shift_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    peak_hourly_volume: Mapped[int] = mapped_column(Integer, default=0)
