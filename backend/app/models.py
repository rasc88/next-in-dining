from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def to_camel(snake: str) -> str:
    head, *tail = snake.split("_")
    return head + "".join(word.capitalize() for word in tail)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PartyState(str, Enum):
    WAITING = "WAITING"
    NOTIFIED = "NOTIFIED"
    SEATED = "SEATED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    EXPIRED = "EXPIRED"


class PartyAction(str, Enum):
    NOTIFY = "NOTIFY"
    SEAT = "SEAT"
    NO_SHOW = "NO_SHOW"
    RE_NOTIFY = "RE_NOTIFY"
    UN_SEAT = "UN_SEAT"


class WaitlistErrorCode(str, Enum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    NOT_FOUND = "NOT_FOUND"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"


class ApiError(CamelModel):
    code: WaitlistErrorCode
    message: str


class HostUser(CamelModel):
    id: str
    email: str


class LoginCredentials(CamelModel):
    email: str
    password: str


class AuthSession(CamelModel):
    token: str
    host: HostUser


class JoinWaitlistInput(CamelModel):
    guest_name: str
    phone_number: str
    party_size: int = Field(ge=1, le=20)
    seating_category: str
    notes: str | None = None


class WaitlistParty(CamelModel):
    id: str
    guest_name: str
    phone_number: str
    party_size: int
    seating_category: str
    notes: str | None = None
    state: PartyState
    created_at: datetime
    notified_at: datetime | None = None
    resolved_at: datetime | None = None
    push_subscribed: bool | None = None


class JoinWaitlistResult(CamelModel):
    party: WaitlistParty
    guest_token: str


class QueueMetrics(CamelModel):
    active_waiting: int
    peak_hourly_volume: int


class ActiveQueue(CamelModel):
    parties: list[WaitlistParty]
    metrics: QueueMetrics


class GuestStatus(WaitlistParty):
    position: int | None
    total_waiting: int


class PushSubscriptionKeys(CamelModel):
    p256dh: str
    auth: str


class PushSubscriptionInput(CamelModel):
    endpoint: str
    expiration_time: float | None = None
    keys: PushSubscriptionKeys


class UpdatePartyStateRequest(CamelModel):
    action: PartyAction
