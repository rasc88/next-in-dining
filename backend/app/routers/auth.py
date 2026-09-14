from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_host_token
from app.models import AuthSession, HostUser, LoginCredentials, WaitlistErrorCode
from app.store import store

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=AuthSession)
def login(credentials: LoginCredentials) -> AuthSession:
    host = store.verify_host_login(credentials.email, credentials.password)
    if host is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": WaitlistErrorCode.INVALID_CREDENTIALS.value,
                "message": "Incorrect email or password.",
            },
        )
    token = store.create_host_token(host.id)
    return AuthSession(token=token, host=HostUser(id=host.id, email=host.email))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(require_host_token)) -> None:
    store.revoke_host_token(token)
