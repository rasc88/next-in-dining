from __future__ import annotations

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

router = APIRouter(prefix="/waitlist")


@router.post(
    "/join",
    response_model=JoinWaitlistResult,
    status_code=status.HTTP_201_CREATED,
    tags=["Waitlist (Host)"],
)
def join_waitlist(payload: JoinWaitlistInput) -> JoinWaitlistResult:
    party, guest_token = store.create_party(
        guest_name=payload.guest_name,
        phone_number=payload.phone_number,
        party_size=payload.party_size,
        seating_category=payload.seating_category,
        notes=payload.notes,
    )
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
    return store.update_party_state(party_id, payload.action)


@router.get("/me", response_model=GuestStatus, tags=["Waitlist (Guest)"])
def get_guest_status(party: WaitlistParty = Depends(require_guest_party)) -> GuestStatus:
    position = store.position_of(party.id)
    total_waiting = len(store.waiting_parties_ordered())
    return GuestStatus(**party.model_dump(), position=position, total_waiting=total_waiting)


@router.post("/me/cancel", response_model=WaitlistParty, tags=["Waitlist (Guest)"])
def cancel_my_party(party: WaitlistParty = Depends(require_guest_party)) -> WaitlistParty:
    return store.cancel_party(party.id)


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
