from __future__ import annotations

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models import WaitlistErrorCode, WaitlistParty

host_bearer_scheme = HTTPBearer(auto_error=False)
guest_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": WaitlistErrorCode.TOKEN_EXPIRED.value, "message": message},
    )


def require_host_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(host_bearer_scheme),
) -> str:
    from app.store import store

    if credentials is None:
        raise _unauthorized("Missing host session token.")
    host = store.get_host_by_token(credentials.credentials)
    if host is None:
        raise _unauthorized("Missing or invalid host session token.")
    return credentials.credentials


def require_guest_party(
    credentials: HTTPAuthorizationCredentials | None = Depends(guest_bearer_scheme),
) -> WaitlistParty:
    from app.store import store

    if credentials is None:
        raise _unauthorized("Missing guest token.")
    party = store.get_party_by_guest_token(credentials.credentials)
    if party is None:
        raise _unauthorized("This guest link is no longer valid.")
    return party
