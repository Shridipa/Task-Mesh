"""Token exchange: API key in, short-lived JWT out."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...config import get_settings
from ..auth import Principal, create_access_token, get_principal
from ..rate_limit import SlidingWindowLimiter, client_key

router = APIRouter()

TOKEN_REQUESTS_PER_WINDOW = 10
TOKEN_WINDOW_SECONDS = 60.0

_limiter = SlidingWindowLimiter(
    limit=TOKEN_REQUESTS_PER_WINDOW, window_seconds=TOKEN_WINDOW_SECONDS
)


class TokenRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - a scheme name, not a credential
    expires_at: int
    subject: str
    role: str
    tenant: str


class IdentityResponse(BaseModel):
    subject: str
    role: str
    tenant: str
    expires_at: int


@router.post("/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, request: Request) -> TokenResponse:
    """Exchange a configured API key for a signed access token."""
    _limiter.check(
        client_key(request),
        "Too many token requests. Please wait a minute and try again.",
    )

    settings = get_settings()
    match: tuple[str, str] | None = None
    for key, value in settings.api_keys.items():
        # Compare every configured key so the loop takes the same time whether
        # or not one matches.
        if hmac.compare_digest(key, payload.api_key):
            match = value
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    role, tenant = match
    # The subject identifies the credential, never the secret itself.
    digest = hashlib.sha256(payload.api_key.encode("utf-8")).hexdigest()[:12]
    token, expires_at = create_access_token(f"api-key:{digest}", role, tenant)
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        subject=f"api-key:{digest}",
        role=role,
        tenant=tenant,
    )


@router.get("/me", response_model=IdentityResponse)
async def whoami(principal: Principal = Depends(get_principal)) -> IdentityResponse:
    """Return the identity carried by the presented token."""
    return IdentityResponse(
        subject=principal.subject,
        role=principal.role,
        tenant=principal.tenant,
        expires_at=principal.expires_at,
    )
