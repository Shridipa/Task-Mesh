"""Authentication and authorization for the TaskMesh API.

Two independent mechanisms are supported, each for a different caller:

* **People and integrations** exchange a long-lived API key for a short-lived
  JSON Web Token at ``POST /auth/token`` and send it as
  ``Authorization: Bearer <token>``. The token carries ``sub``, ``role`` and
  ``tenant`` claims; the signature, issuer, audience and expiry are all
  verified on every request, so a client can never simply claim a role.
* **Workers** send the shared ``X-Worker-Token`` secret, compared in constant
  time.

The old behaviour of trusting a client-supplied ``X-Role`` header is gone: that
header is ignored entirely.
"""

from __future__ import annotations

import hmac
import logging
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import get_settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

ROLE_HIERARCHY: dict[str, set[str]] = {
    "admin": {"admin", "developer", "viewer"},
    "developer": {"developer", "viewer"},
    "viewer": {"viewer"},
}

WRITE_ROLES = {"admin", "developer"}
READ_ROLES = {"admin", "developer", "viewer"}

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")


class InvalidToken(Exception):
    """Raised when a bearer token cannot be trusted."""


@dataclass(frozen=True)
class Principal:
    """The authenticated caller."""

    subject: str
    role: str
    tenant: str
    expires_at: int

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def create_access_token(subject: str, role: str, tenant: str) -> tuple[str, int]:
    """Sign a short-lived access token and return ``(token, expires_at)``."""
    settings = get_settings()
    now = int(time.time())
    expires_at = now + settings.jwt_ttl_seconds
    payload = {
        "sub": subject,
        "role": role,
        "tenant": tenant,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> Principal:
    """Verify a token's signature and claims, returning the caller."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        # Never echo the token or the secret; the reason is enough for logs.
        raise InvalidToken(str(exc)) from exc

    role = claims.get("role")
    if role not in ROLE_HIERARCHY:
        raise InvalidToken(f"token carries an unknown role: {role!r}")
    tenant = claims.get("tenant") or "default"
    return Principal(
        subject=str(claims["sub"]),
        role=role,
        tenant=str(tenant),
        expires_at=int(claims["exp"]),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    """Resolve the caller from the ``Authorization: Bearer`` header."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Authentication required")
    try:
        return decode_access_token(credentials.credentials)
    except InvalidToken as exc:
        logger.info("Rejected bearer token: %s", exc)
        raise _unauthorized("Invalid or expired token") from exc


async def require_read_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal | None:
    """Return the caller if a valid token is present, otherwise ``None``.

    A token that is present but invalid is still rejected: optional
    authentication must never accept a forged credential.
    """
    if credentials is None or not credentials.credentials:
        return None
    try:
        return decode_access_token(credentials.credentials)
    except InvalidToken as exc:
        logger.info("Rejected bearer token: %s", exc)
        raise _unauthorized("Invalid or expired token") from exc


def require_role(required_roles: set[str]):
    """Dependency factory enforcing role-based access control."""

    async def _check(principal: Principal = Depends(get_principal)) -> Principal:
        allowed = ROLE_HIERARCHY.get(principal.role, set())
        if not (allowed & required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return principal

    return _check


require_admin = require_role({"admin"})
require_write = require_role(WRITE_ROLES)
require_read = require_role(READ_ROLES)


def require_worker_token(request: Request) -> str:
    """Validate the shared worker secret in ``X-Worker-Token`` (constant time)."""
    settings = get_settings()
    supplied = request.headers.get("x-worker-token")
    if not supplied:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Worker-Token header",
        )
    if not hmac.compare_digest(supplied, settings.worker_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid worker token")
    return supplied


def worker_identity(request: Request) -> str:
    """Identify the calling worker, for lease ownership checks."""
    return request.headers.get("x-worker-id") or "api-worker"


def tenant_scope(principal: Principal, requested: str | None) -> str | None:
    """Constrain a query to the caller's tenant unless it is an administrator."""
    if principal.is_admin:
        return requested
    return principal.tenant
