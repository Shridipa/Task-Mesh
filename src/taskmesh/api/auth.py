"""Shared auth dependencies for TaskMesh API."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

ROLE_HIERARCHY = {
    "admin": {"admin", "developer", "viewer"},
    "developer": {"developer", "viewer"},
    "viewer": {"viewer"},
}

WRITE_ROLES = {"admin", "developer"}
READ_ROLES = {"admin", "developer", "viewer"}
WORKER_ROLES = {"worker"}


def require_role(required_roles: set[str]):
    """Dependency factory for role-based access control using X-Role header."""
    async def _check_role(request: Request) -> str:
        x_role = request.headers.get("x-role")
        if not x_role:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Role header")
        if x_role not in ROLE_HIERARCHY and x_role != "worker":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unknown role: {x_role}")
        allowed = ROLE_HIERARCHY.get(x_role, set())
        if not (allowed & required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return x_role
    return _check_role


require_admin = require_role({"admin"})
require_write = require_role(WRITE_ROLES)
require_read = require_role(READ_ROLES)
require_worker = require_role(WORKER_ROLES)


def require_worker_token(worker_secret: str):
    """Validate worker token for worker-specific endpoints using X-Worker-Token header."""
    async def _check_token(request: Request) -> str:
        x_worker_token = request.headers.get("x-worker-token")
        if not x_worker_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Worker-Token header")
        if x_worker_token != worker_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid worker token")
        return x_worker_token
    return _check_token
