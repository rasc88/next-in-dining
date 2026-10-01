from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status

from app.auth import require_guest_party, require_host_token
from app.models import (
    ActiveQueue,
    GuestStatus,
    JoinWaitlistInput,
    JoinWaitlistResult,
    PushSubscriptionInput,
    UpdatePartyStateRequest,
    WaitlistParty,
)
from app.store import store
from app.telemetry import METRIC_ATTRIBUTES, parties_created, party_creation_failures, party_transitions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/waitlist")


@router.post(
    "/join",
    response_model=JoinWaitlistResult,
    status_code=status.HTTP_201_CREATED,
    tags=["Waitlist (Host)"],
)
def join_waitlist(payload: JoinWaitlistInput) -> JoinWaitlistResult:
    try:
        party, guest_token = store.create_party(
            guest_name=payload.guest_name,
            phone_number=payload.phone_number,
            party_size=payload.party_size,
            seating_category=payload.seating_category,
            notes=payload.notes,
        )
    except Exception:
        party_creation_failures.add(1, METRIC_ATTRIBUTES)
        logger.exception("Failed to create party")
        raise
    parties_created.add(1, METRIC_ATTRIBUTES)
    return JoinWaitlistResult(party=party, guest_token=guest_token)


@router.get(
    "/active",
    response_model=ActiveQueue,
    tags=["Waitlist (Host)"],
    dependencies=[Depends(require_host_token)],
)
def get_active_parties() -> ActiveQueue:
    return ActiveQueue(parties=store.list_active_parties(), metrics=store.metrics())


@router.patch(
    "/{party_id}/state",
    response_model=WaitlistParty,
    tags=["Waitlist (Host)"],
    dependencies=[Depends(require_host_token)],
)
def update_party_state(party_id: str, payload: UpdatePartyStateRequest) -> WaitlistParty:
    party = store.update_party_state(party_id, payload.action)
    party_transitions.add(1, {**METRIC_ATTRIBUTES, "to_state": party.state.value})
    return party


@router.get("/me", response_model=GuestStatus, tags=["Waitlist (Guest)"])
def get_guest_status(party: WaitlistParty = Depends(require_guest_party)) -> GuestStatus:
    position = store.position_of(party.id)
    total_waiting = len(store.waiting_parties_ordered())
    return GuestStatus(**party.model_dump(), position=position, total_waiting=total_waiting)


@router.post("/me/cancel", response_model=WaitlistParty, tags=["Waitlist (Guest)"])
def cancel_my_party(party: WaitlistParty = Depends(require_guest_party)) -> WaitlistParty:
    cancelled = store.cancel_party(party.id)
    party_transitions.add(1, {**METRIC_ATTRIBUTES, "to_state": cancelled.state.value})
    return cancelled


@router.post(
    "/me/push-subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Waitlist (Guest)"],
)
def subscribe_push(
    subscription: PushSubscriptionInput,
    party: WaitlistParty = Depends(require_guest_party),
) -> None:
    store.save_push_subscription(party.id, subscription.model_dump())
