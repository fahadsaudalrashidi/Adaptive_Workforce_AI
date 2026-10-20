"""
AWI Enterprise Authentication API — Phase 30.1
Login, logout, token refresh, password management, and user administration.
All endpoints operate against the local SQLite auth store — no external calls.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, field_validator

from backend.core.local_auth import (
    LocalUser,
    LoginResult,
    get_auth_manager,
    validate_password_strength,
    create_refresh_token,
    decode_token,
)
from backend.core.auth_session import AWIRole
from backend.core.security_middleware import (
    get_current_user,
    require_role,
    optional_auth,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 28800  # 8 hours in seconds
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    email: str
    role: str
    initial_password: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {r.value for r in AWIRole}
        if v not in valid:
            raise ValueError(f"Invalid role. Must be one of: {sorted(valid)}")
        return v


class UpdateRoleRequest(BaseModel):
    new_role: str

    @field_validator("new_role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {r.value for r in AWIRole}
        if v not in valid:
            raise ValueError(f"Invalid role. Must be one of: {sorted(valid)}")
        return v


class ResetPasswordRequest(BaseModel):
    new_password: str
    force_change: bool = True


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request):
    """Authenticate with username + password. Returns JWT access and refresh tokens."""
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("User-Agent", "")

    auth = get_auth_manager()
    result: LoginResult = auth.login(
        username=body.username,
        password=body.password,
        ip_address=ip,
        user_agent=ua,
    )

    if not result.success:
        code = (
            status.HTTP_423_LOCKED
            if result.account_locked
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code=code, detail=result.error_message)

    user = result.user
    return LoginResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user={
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role.value,
            "must_change_password": user.must_change_pw,
        },
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, current_user: LocalUser = Depends(get_current_user)):
    """Revoke the current access token. Client must discard both tokens."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    auth = get_auth_manager()
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            auth.logout(jti=jti, user_id=current_user.user_id)
    except Exception:
        pass  # token already invalid — still return 204


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(body: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token.
    The old refresh token is revoked; a fresh pair is issued.
    """
    auth = get_auth_manager()
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token"
        )

    jti = payload.get("jti")
    if jti and auth.is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked"
        )

    user_id = payload.get("sub")
    user = auth.get_user_by_id(user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
        )

    # Revoke old refresh token
    if jti:
        auth.logout(jti=jti, user_id=user.user_id)

    # Issue new token pair
    from backend.core.local_auth import create_access_token
    new_access, new_access_jti = create_access_token(
        user.user_id, user.username, user.role, user.must_change_pw
    )
    new_refresh, new_refresh_jti = create_refresh_token(user.user_id)

    # Persist new tokens
    auth._persist_token(new_access_jti, user.user_id, "access", 8 * 3600)
    auth._persist_token(new_refresh_jti, user.user_id, "refresh", 30 * 86400)

    return LoginResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user={
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role.value,
            "must_change_password": user.must_change_pw,
        },
    )


@router.get("/me")
def get_me(current_user: LocalUser = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "role": current_user.role.value,
        "must_change_password": current_user.must_change_pw,
        "last_login": current_user.last_login,
    }


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    current_user: LocalUser = Depends(get_current_user),
):
    """Change the authenticated user's own password."""
    auth = get_auth_manager()
    ok, msg = auth.change_password(
        user_id=current_user.user_id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


# ---------------------------------------------------------------------------
# User management endpoints (SYSTEM_ADMIN only)
# ---------------------------------------------------------------------------

@router.get("/users")
def list_users(
    active_only: bool = True,
    _: LocalUser = Depends(require_role(AWIRole.SYSTEM_ADMIN, AWIRole.CHRO)),
):
    """List all users. CHRO and SYSTEM_ADMIN only."""
    auth = get_auth_manager()
    users = auth.list_users(active_only=active_only)
    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role.value,
            "is_active": u.is_active,
            "must_change_password": u.must_change_pw,
            "last_login": u.last_login,
        }
        for u in users
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    current_user: LocalUser = Depends(require_role(AWIRole.SYSTEM_ADMIN)),
):
    """Create a new user. SYSTEM_ADMIN only."""
    ok, msg = validate_password_strength(body.initial_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    auth = get_auth_manager()
    try:
        user = auth.create_user(
            username=body.username,
            display_name=body.display_name,
            email=body.email,
            role=AWIRole(body.role),
            initial_password=body.initial_password,
            must_change_pw=True,
            creator_user_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value,
    }


@router.patch("/users/{user_id}/role", status_code=status.HTTP_204_NO_CONTENT)
def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    current_user: LocalUser = Depends(require_role(AWIRole.SYSTEM_ADMIN)),
):
    """Change a user's role. SYSTEM_ADMIN only."""
    auth = get_auth_manager()
    ok = auth.update_role(
        user_id=user_id,
        new_role=AWIRole(body.new_role),
        changed_by=current_user.user_id,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: str,
    current_user: LocalUser = Depends(require_role(AWIRole.SYSTEM_ADMIN)),
):
    """Deactivate a user account. SYSTEM_ADMIN only."""
    auth = get_auth_manager()
    ok = auth.deactivate_user(user_id=user_id, deactivated_by=current_user.user_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: str,
    body: ResetPasswordRequest,
    current_user: LocalUser = Depends(require_role(AWIRole.SYSTEM_ADMIN)),
):
    """Force-reset a user's password. SYSTEM_ADMIN only."""
    ok, msg = validate_password_strength(body.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    auth = get_auth_manager()
    ok = auth.reset_password(
        user_id=user_id,
        new_password=body.new_password,
        reset_by=current_user.user_id,
        force_change=body.force_change,
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


@router.post("/users/{username}/unlock", status_code=status.HTTP_204_NO_CONTENT)
def unlock_user(
    username: str,
    current_user: LocalUser = Depends(require_role(AWIRole.SYSTEM_ADMIN)),
):
    """Manually unlock a locked account. SYSTEM_ADMIN only."""
    auth = get_auth_manager()
    ok = auth.unlock_account(username=username, admin_user_id=current_user.user_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


# ---------------------------------------------------------------------------
# Security audit log (read-only for auditors and above)
# ---------------------------------------------------------------------------

@router.get("/audit-log")
def get_audit_log(
    limit: int = 100,
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: LocalUser = Depends(
        require_role(
            AWIRole.AUDITOR,
            AWIRole.CHRO,
            AWIRole.SYSTEM_ADMIN,
        )
    ),
):
    """
    Retrieve the security audit log.
    Accessible to AUDITOR, CHRO, and SYSTEM_ADMIN.
    """
    auth = get_auth_manager()
    entries = auth.get_security_audit_log(
        limit=min(limit, 1000),
        event_type=event_type,
        user_id=user_id,
    )
    return {"total": len(entries), "entries": entries}


# ---------------------------------------------------------------------------
# Bootstrap endpoint — called once after fresh deployment
# ---------------------------------------------------------------------------

@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
def bootstrap(initial_password: str):
    """
    First-boot only: create the initial admin account.
    Idempotent — safe to call again if admin already exists.
    Disable this endpoint in production after initial setup.
    """
    ok, msg = validate_password_strength(initial_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    auth = get_auth_manager()
    try:
        user = auth.bootstrap_admin(initial_password=initial_password)
        return {
            "created": True,
            "username": user.username,
            "role": user.role.value,
            "must_change_password": user.must_change_pw,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        )
