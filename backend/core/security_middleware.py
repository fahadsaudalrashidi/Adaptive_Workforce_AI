"""
AWI Enterprise Security Middleware — Phase 30.1
FastAPI dependency injection for JWT validation and RBAC enforcement.
Designed for fully local on-premises deployment — no external IdP calls.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.local_auth import LocalUser, get_auth_manager
from backend.core.auth_session import AWIRole, PERMISSION_MATRIX

_bearer_scheme = HTTPBearer(auto_error=False)

# AUTH_ENFORCED can be toggled to False in tests or during initial deployment.
# In production this should always be True.
# Checked at request time (not module load) so test overrides work without reloading.
def _auth_enforced() -> bool:
    return os.environ.get("AWI_AUTH_ENFORCED", "true").lower() != "false"

AUTH_ENFORCED: bool = True  # kept for backwards compat; runtime uses _auth_enforced()


# ---------------------------------------------------------------------------
# Core dependency — resolve current user from Bearer token
# ---------------------------------------------------------------------------

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> LocalUser:
    """
    FastAPI dependency — extracts and validates the Bearer JWT from the
    Authorization header.  Raises HTTP 401 if the token is missing, expired,
    revoked, or otherwise invalid.
    """
    if not _auth_enforced():
        # During initial rollout / integration testing, return a synthetic
        # admin user so that un-authed callers still reach the endpoint.
        return _synthetic_admin()

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    auth_manager = get_auth_manager()
    user, error = auth_manager.verify_token_and_get_user(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[LocalUser]:
    """
    Dependency for endpoints that work both authenticated and unauthenticated.
    Returns the resolved LocalUser if a valid token is present, else None.
    Used during the auth transition period.
    """
    if not _auth_enforced() or credentials is None:
        return None

    token = credentials.credentials
    auth_manager = get_auth_manager()
    user, _ = auth_manager.verify_token_and_get_user(token)
    return user


# ---------------------------------------------------------------------------
# RBAC enforcement factories
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: AWIRole):
    """
    Factory that returns a FastAPI dependency enforcing that the authenticated
    user holds one of the specified roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(AWIRole.SYSTEM_ADMIN))])
        def admin_endpoint(): ...
    """
    def _check(user: LocalUser = Depends(get_current_user)) -> LocalUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' is not authorised for this resource",
            )
        return user
    return _check


def require_permission(permission: str):
    """
    Factory that returns a FastAPI dependency enforcing that the authenticated
    user's role has the given permission in PERMISSION_MATRIX.

    Usage:
        @router.post("/users", dependencies=[Depends(require_permission("manage_users"))])
        def create_user(): ...
    """
    def _check(user: LocalUser = Depends(get_current_user)) -> LocalUser:
        # PERMISSION_MATRIX structure: {permission_name: [roles_that_have_it]}
        # SYSTEM_ADMIN bypasses all checks
        from backend.core.auth_session import AWIRole as _AWIRole
        if user.role == _AWIRole.SYSTEM_ADMIN:
            return user
        allowed_roles = PERMISSION_MATRIX.get(permission, [])
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user
    return _check


# ---------------------------------------------------------------------------
# Convenience role dependencies (importable directly)
# ---------------------------------------------------------------------------

RequireSystemAdmin = Depends(require_role(AWIRole.SYSTEM_ADMIN))
RequireCHRO = Depends(require_role(AWIRole.CHRO, AWIRole.SYSTEM_ADMIN))
RequireExecutive = Depends(
    require_role(AWIRole.EXECUTIVE, AWIRole.CHRO, AWIRole.SYSTEM_ADMIN)
)
RequireHRManager = Depends(
    require_role(
        AWIRole.HR_MANAGER, AWIRole.CHRO, AWIRole.EXECUTIVE, AWIRole.SYSTEM_ADMIN
    )
)
RequireAnalyst = Depends(
    require_role(
        AWIRole.HR_ANALYST,
        AWIRole.HR_MANAGER,
        AWIRole.CHRO,
        AWIRole.EXECUTIVE,
        AWIRole.SYSTEM_ADMIN,
    )
)
RequireAuditor = Depends(
    require_role(
        AWIRole.AUDITOR,
        AWIRole.HR_MANAGER,
        AWIRole.CHRO,
        AWIRole.EXECUTIVE,
        AWIRole.SYSTEM_ADMIN,
    )
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _synthetic_admin() -> LocalUser:
    """Return a lightweight synthetic admin user when auth is disabled."""
    from backend.core.local_auth import LocalUser
    import uuid
    return LocalUser(
        user_id=str(uuid.UUID(int=0)),
        username="dev_admin",
        display_name="Development Admin",
        email="dev@awi.local",
        role=AWIRole.SYSTEM_ADMIN,
        is_active=True,
        must_change_pw=False,
        created_at="1970-01-01T00:00:00",
        last_login=None,
    )
