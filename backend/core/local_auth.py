"""
AWI Local Authentication Engine — Phase 30.1 Enterprise License Hardening.

Enterprise on-premises authentication for single-organisation deployments.
No external identity provider required. Fully offline capable.

Capabilities:
  - Local user accounts with bcrypt-hashed passwords (cost factor 12)
  - JWT Bearer tokens (HS256, deployment-specific secret)
  - Configurable session TTL (default 8 hours)
  - Login attempt tracking with automatic lockout (5 attempts → 15-minute lockout)
  - Full RBAC role assignment per user
  - Audit logging for all authentication events
  - First-boot admin bootstrap with forced password change
  - Secure deployment secret generation (written to data/awi_secret.key on first start)

Enterprise deployment model:
  - Each customer receives their own isolated deployment
  - Credentials never leave the customer's infrastructure
  - No SaaS, no shared environment, no cloud calls
  - Air-gapped network compatible

Database: data/awi_auth.db (SQLite, WAL mode)
Secret:   data/awi_secret.key (deployment-specific HMAC key, 256-bit)
"""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Guards for optional security dependencies ─────────────────────────────────
try:
    from passlib.context import CryptContext
    _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
    _HAS_PASSLIB = True
except ImportError:
    _HAS_PASSLIB = False
    _pwd_context = None  # type: ignore
    logger.warning("passlib not installed — password hashing unavailable")

try:
    from jose import jwt, JWTError
    _HAS_JOSE = True
except ImportError:
    _HAS_JOSE = False
    jwt = None  # type: ignore
    JWTError = Exception  # type: ignore
    logger.warning("python-jose not installed — JWT unavailable")

# ── Re-export AWIRole from auth_session ──────────────────────────────────────
from backend.core.auth_session import AWIRole, PERMISSION_MATRIX

# ── Paths ─────────────────────────────────────────────────────────────────────
_DATA_DIR   = Path(__file__).resolve().parent.parent.parent / "data"
_DB_PATH    = _DATA_DIR / "awi_auth.db"
_SECRET_KEY_PATH = _DATA_DIR / "awi_secret.key"

# ── Constants ─────────────────────────────────────────────────────────────────
_JWT_ALGORITHM        = "HS256"
_ACCESS_TOKEN_MINUTES = 480          # 8 hours
_REFRESH_TOKEN_DAYS   = 30
_LOCKOUT_MAX_ATTEMPTS = 5
_LOCKOUT_WINDOW_MINS  = 15           # count attempts within this window
_LOCKOUT_DURATION_MINS = 15          # lock account for this long
_BCRYPT_ROUNDS        = 12


# ── Deployment secret management ──────────────────────────────────────────────

def _load_or_create_secret() -> str:
    """Load deployment JWT secret from file, or generate and persist a new one."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if _SECRET_KEY_PATH.exists():
        return _SECRET_KEY_PATH.read_text(encoding="ascii").strip()
    # Generate 256-bit (32-byte) cryptographically secure secret
    secret = secrets.token_hex(32)
    _SECRET_KEY_PATH.write_text(secret, encoding="ascii")
    # Restrict permissions on Unix (no-op on Windows)
    try:
        os.chmod(_SECRET_KEY_PATH, 0o600)
    except OSError:
        pass
    logger.info("AWI: Generated new deployment secret at %s", _SECRET_KEY_PATH)
    return secret


_JWT_SECRET: str = _load_or_create_secret()


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class LocalUser:
    user_id:          str
    username:         str
    display_name:     str
    email:            str
    role:             AWIRole
    is_active:        bool      = True
    must_change_pw:   bool      = True   # True on first login / after admin reset
    created_at:       str       = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login:       str | None = None
    failed_attempts:  int       = 0
    locked_until:     str | None = None


@dataclass
class TokenPair:
    access_token:  str
    refresh_token: str
    token_type:    str = "bearer"
    expires_in:    int = _ACCESS_TOKEN_MINUTES * 60  # seconds


@dataclass
class LoginResult:
    success:         bool
    user:            LocalUser | None = None
    tokens:          TokenPair | None = None
    error:           str | None       = None
    locked_until:    str | None       = None
    must_change_pw:  bool             = False
    account_locked:  bool             = False

    # Convenience accessors so callers can use result.access_token directly
    @property
    def access_token(self) -> str | None:
        return self.tokens.access_token if self.tokens else None

    @property
    def refresh_token(self) -> str | None:
        return self.tokens.refresh_token if self.tokens else None

    @property
    def error_message(self) -> str | None:
        return self.error


# ── Database ──────────────────────────────────────────────────────────────────

def _get_db_path() -> Path:
    """Return DB path; env var AWI_AUTH_DB overrides default (used in tests)."""
    env = os.environ.get("AWI_AUTH_DB", "")
    return Path(env) if env else _DB_PATH


def _connect() -> sqlite3.Connection:
    db = _get_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema() -> None:
    """Create tables if they do not exist. Idempotent."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awi_local_users (
                user_id         TEXT PRIMARY KEY,
                username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name    TEXT NOT NULL,
                email           TEXT NOT NULL,
                role            TEXT NOT NULL,
                password_hash   TEXT NOT NULL,
                is_active       INTEGER NOT NULL DEFAULT 1,
                must_change_pw  INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL,
                last_login      TEXT,
                UNIQUE (email COLLATE NOCASE)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awi_login_attempts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT NOT NULL COLLATE NOCASE,
                attempted_at    TEXT NOT NULL,
                success         INTEGER NOT NULL DEFAULT 0,
                ip_address      TEXT,
                user_agent      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awi_account_locks (
                username        TEXT PRIMARY KEY COLLATE NOCASE,
                locked_at       TEXT NOT NULL,
                locked_until    TEXT NOT NULL,
                reason          TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awi_active_tokens (
                jti             TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                token_type      TEXT NOT NULL DEFAULT 'access',
                issued_at       TEXT NOT NULL,
                expires_at      TEXT NOT NULL,
                revoked         INTEGER NOT NULL DEFAULT 0,
                ip_address      TEXT,
                user_agent      TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awi_security_audit (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT NOT NULL,
                username    TEXT,
                user_id     TEXT,
                ip_address  TEXT,
                user_agent  TEXT,
                detail      TEXT,
                occurred_at TEXT NOT NULL
            )
        """)
        # Indexes for frequent queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_username ON awi_login_attempts(username, attempted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_active_tokens_user ON awi_active_tokens(user_id, revoked)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_security_audit_type ON awi_security_audit(event_type, occurred_at)")
        conn.commit()


# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (cost=12)."""
    if not _HAS_PASSLIB:
        raise RuntimeError("passlib[bcrypt] is required for password hashing")
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not _HAS_PASSLIB:
        raise RuntimeError("passlib[bcrypt] is required for password verification")
    return _pwd_context.verify(plain, hashed)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Enforce enterprise password policy.
    Min 10 chars, upper+lower+digit+special required.
    """
    if len(password) < 10:
        return False, "Password must be at least 10 characters."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit."
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        return False, "Password must contain at least one special character."
    return True, "OK"


# ── JWT utilities ─────────────────────────────────────────────────────────────

def _make_jti() -> str:
    return secrets.token_hex(16)


def create_access_token(user_id: str, username: str, role: str,
                        must_change_pw: bool = False) -> tuple[str, str]:
    """
    Issue a JWT access token.
    Returns (token_string, jti).
    """
    if not _HAS_JOSE:
        raise RuntimeError("python-jose is required for JWT tokens")
    now = datetime.now(timezone.utc)
    jti = _make_jti()
    payload = {
        "sub":            user_id,
        "username":       username,
        "role":           role,
        "must_change_pw": must_change_pw,
        "jti":            jti,
        "iat":            int(now.timestamp()),
        "exp":            int((now + timedelta(minutes=_ACCESS_TOKEN_MINUTES)).timestamp()),
        "type":           "access",
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
    return token, jti


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Issue a JWT refresh token. Returns (token_string, jti)."""
    if not _HAS_JOSE:
        raise RuntimeError("python-jose is required for JWT tokens")
    now = datetime.now(timezone.utc)
    jti = _make_jti()
    payload = {
        "sub":  user_id,
        "jti":  jti,
        "iat":  int(now.timestamp()),
        "exp":  int((now + timedelta(days=_REFRESH_TOKEN_DAYS)).timestamp()),
        "type": "refresh",
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises JWTError on invalid/expired tokens.
    """
    if not _HAS_JOSE:
        raise RuntimeError("python-jose is required for JWT tokens")
    return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])


# ── Lockout management ────────────────────────────────────────────────────────

def _is_locked(username: str) -> tuple[bool, str | None]:
    """Return (is_locked, locked_until_iso) for a username."""
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        row = conn.execute(
            "SELECT locked_until FROM awi_account_locks WHERE username=? COLLATE NOCASE",
            (username,)
        ).fetchone()
        if row is None:
            return False, None
        locked_until = datetime.fromisoformat(row["locked_until"])
        if now < locked_until:
            return True, row["locked_until"]
        # Lock expired — remove it
        conn.execute("DELETE FROM awi_account_locks WHERE username=? COLLATE NOCASE", (username,))
        conn.commit()
        return False, None


def _record_attempt(username: str, success: bool,
                    ip_address: str | None = None,
                    user_agent: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO awi_login_attempts (username, attempted_at, success, ip_address, user_agent) "
            "VALUES (?,?,?,?,?)",
            (username, now, int(success), ip_address, user_agent),
        )
        conn.commit()


def _check_and_apply_lockout(username: str) -> bool:
    """
    Count recent failed attempts. If >= threshold, apply lockout.
    Returns True if account is now locked.
    """
    window_start = (datetime.now(timezone.utc) - timedelta(minutes=_LOCKOUT_WINDOW_MINS)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM awi_login_attempts "
            "WHERE username=? COLLATE NOCASE AND success=0 AND attempted_at>=?",
            (username, window_start),
        ).fetchone()
        n_fails = row["n"] if row else 0
        if n_fails >= _LOCKOUT_MAX_ATTEMPTS:
            now = datetime.now(timezone.utc)
            locked_until = (now + timedelta(minutes=_LOCKOUT_DURATION_MINS)).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO awi_account_locks (username, locked_at, locked_until, reason) "
                "VALUES (?,?,?,?)",
                (username, now.isoformat(), locked_until,
                 f"Automatic: {n_fails} failed attempts within {_LOCKOUT_WINDOW_MINS} minutes"),
            )
            conn.commit()
            _audit("account_locked", username=username,
                   detail=f"Locked after {n_fails} failed attempts")
            return True
    return False


# ── Audit logging ─────────────────────────────────────────────────────────────

def _audit(event_type: str, username: str | None = None, user_id: str | None = None,
           ip_address: str | None = None, user_agent: str | None = None,
           detail: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO awi_security_audit "
                "(event_type,username,user_id,ip_address,user_agent,detail,occurred_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (event_type, username, user_id, ip_address, user_agent, detail, now),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Security audit write failed (non-fatal): %s", exc)


# ── LocalAuthManager — public API ─────────────────────────────────────────────

class LocalAuthManager:
    """
    Enterprise local authentication manager.
    One instance per deployment (singleton pattern via module-level instance).
    """

    def __init__(self) -> None:
        _ensure_schema()

    # ── User management ───────────────────────────────────────────────────────

    def create_user(
        self,
        username: str,
        display_name: str,
        email: str,
        role: AWIRole,
        initial_password: str,
        must_change_pw: bool = True,
        creator_user_id: str | None = None,
    ) -> LocalUser:
        """Create a new local user. Password is bcrypt-hashed before storage."""
        pw_ok, pw_msg = validate_password_strength(initial_password)
        if not pw_ok:
            raise ValueError(f"Password policy violation: {pw_msg}")
        import uuid
        user_id = str(uuid.uuid4())
        pw_hash = hash_password(initial_password)
        now     = datetime.now(timezone.utc).isoformat()
        try:
            with _connect() as conn:
                conn.execute(
                    "INSERT INTO awi_local_users "
                    "(user_id,username,display_name,email,role,password_hash,is_active,must_change_pw,created_at) "
                    "VALUES (?,?,?,?,?,?,1,?,?)",
                    (user_id, username, display_name, email, role.value,
                     pw_hash, int(must_change_pw), now),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"User already exists (duplicate username or email): {exc}") from exc
        _audit("user_created", username=username, user_id=user_id,
               detail=f"role={role.value} creator={creator_user_id}")
        return self.get_user_by_id(user_id)  # type: ignore

    def get_user_by_id(self, user_id: str) -> LocalUser | None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM awi_local_users WHERE user_id=?", (user_id,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_username(self, username: str) -> LocalUser | None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM awi_local_users WHERE username=? COLLATE NOCASE",
                (username,),
            ).fetchone()
        return self._row_to_user(row) if row else None

    def list_users(self, active_only: bool = True) -> list[LocalUser]:
        with _connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM awi_local_users WHERE is_active=1 ORDER BY username"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM awi_local_users ORDER BY username"
                ).fetchall()
        return [self._row_to_user(r) for r in rows]

    def update_role(self, user_id: str, new_role: AWIRole,
                    changed_by: str | None = None) -> bool:
        with _connect() as conn:
            cur = conn.execute(
                "UPDATE awi_local_users SET role=? WHERE user_id=?",
                (new_role.value, user_id),
            )
            conn.commit()
        if cur.rowcount > 0:
            _audit("role_changed", user_id=user_id,
                   detail=f"new_role={new_role.value} changed_by={changed_by}")
        return cur.rowcount > 0

    def deactivate_user(self, user_id: str, deactivated_by: str | None = None) -> bool:
        with _connect() as conn:
            cur = conn.execute(
                "UPDATE awi_local_users SET is_active=0 WHERE user_id=?", (user_id,)
            )
            conn.commit()
        if cur.rowcount > 0:
            _audit("user_deactivated", user_id=user_id,
                   detail=f"deactivated_by={deactivated_by}")
        return cur.rowcount > 0

    def reset_password(self, user_id: str, new_password: str,
                       reset_by: str | None = None, force_change: bool = True) -> bool:
        """Admin-initiated password reset. Forces must_change_pw=True by default."""
        pw_ok, pw_msg = validate_password_strength(new_password)
        if not pw_ok:
            raise ValueError(f"Password policy violation: {pw_msg}")
        pw_hash = hash_password(new_password)
        with _connect() as conn:
            cur = conn.execute(
                "UPDATE awi_local_users SET password_hash=?, must_change_pw=? WHERE user_id=?",
                (pw_hash, int(force_change), user_id),
            )
            conn.commit()
        if cur.rowcount > 0:
            _audit("password_reset", user_id=user_id,
                   detail=f"reset_by={reset_by} force_change={force_change}")
        return cur.rowcount > 0

    def change_password(self, user_id: str, current_password: str,
                        new_password: str) -> tuple[bool, str]:
        """User self-service password change. Verifies current password."""
        with _connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM awi_local_users WHERE user_id=? AND is_active=1",
                (user_id,),
            ).fetchone()
        if row is None:
            return False, "User not found."
        if not verify_password(current_password, row["password_hash"]):
            _audit("password_change_failed", user_id=user_id,
                   detail="Wrong current password")
            return False, "Current password is incorrect."
        pw_ok, pw_msg = validate_password_strength(new_password)
        if not pw_ok:
            return False, f"Password policy violation: {pw_msg}"
        pw_hash = hash_password(new_password)
        with _connect() as conn:
            conn.execute(
                "UPDATE awi_local_users SET password_hash=?, must_change_pw=0 WHERE user_id=?",
                (pw_hash, user_id),
            )
            conn.commit()
        _audit("password_changed", user_id=user_id, detail="Self-service change")
        return True, "Password changed successfully."

    # ── Authentication ─────────────────────────────────────────────────────────

    def login(self, username: str, password: str,
              ip_address: str | None = None,
              user_agent: str | None = None) -> LoginResult:
        """
        Authenticate a user. Returns tokens on success.
        Implements lockout after _LOCKOUT_MAX_ATTEMPTS failures.
        """
        # Check lockout first
        is_locked, locked_until = _is_locked(username)
        if is_locked:
            _audit("login_blocked", username=username, ip_address=ip_address,
                   detail=f"Locked until {locked_until}")
            return LoginResult(
                success=False,
                error=f"Account temporarily locked. Try again after {locked_until}.",
                locked_until=locked_until,
                account_locked=True,
            )

        # Fetch user
        user = self.get_user_by_username(username)
        if user is None or not user.is_active:
            # Constant-time response to prevent username enumeration
            _record_attempt(username, False, ip_address, user_agent)
            _check_and_apply_lockout(username)
            _audit("login_failed", username=username, ip_address=ip_address,
                   detail="Unknown username or inactive account")
            return LoginResult(success=False, error="Invalid username or password.")

        # Verify password
        with _connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM awi_local_users WHERE user_id=?",
                (user.user_id,),
            ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            _record_attempt(username, False, ip_address, user_agent)
            now_locked = _check_and_apply_lockout(username)
            _audit("login_failed", username=username, user_id=user.user_id,
                   ip_address=ip_address, detail="Wrong password")
            if now_locked:
                return LoginResult(
                    success=False,
                    error=f"Account locked after too many failed attempts. Try again in {_LOCKOUT_DURATION_MINS} minutes.",
                    account_locked=True,
                )
            return LoginResult(success=False, error="Invalid username or password.")

        # Success
        _record_attempt(username, True, ip_address, user_agent)
        now_str = datetime.now(timezone.utc).isoformat()
        with _connect() as conn:
            conn.execute(
                "UPDATE awi_local_users SET last_login=? WHERE user_id=?",
                (now_str, user.user_id),
            )
            conn.commit()

        access_token, access_jti   = create_access_token(
            user.user_id, user.username, user.role.value, user.must_change_pw
        )
        refresh_token, refresh_jti = create_refresh_token(user.user_id)

        # Persist token records for revocation support
        self._persist_token(access_jti, user.user_id, "access",
                            _ACCESS_TOKEN_MINUTES, ip_address, user_agent)
        self._persist_token(refresh_jti, user.user_id, "refresh",
                            _REFRESH_TOKEN_DAYS * 24 * 60, ip_address, user_agent)

        _audit("login_success", username=username, user_id=user.user_id,
               ip_address=ip_address, user_agent=user_agent)

        user.last_login = now_str
        return LoginResult(
            success=True,
            user=user,
            tokens=TokenPair(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
            must_change_pw=user.must_change_pw,
        )

    def logout(self, jti: str, user_id: str) -> None:
        """Revoke a token (add to revocation record)."""
        with _connect() as conn:
            conn.execute(
                "UPDATE awi_active_tokens SET revoked=1 WHERE jti=?", (jti,)
            )
            conn.commit()
        _audit("logout", user_id=user_id, detail=f"jti={jti}")

    def is_token_revoked(self, jti: str) -> bool:
        with _connect() as conn:
            row = conn.execute(
                "SELECT revoked FROM awi_active_tokens WHERE jti=?", (jti,)
            ).fetchone()
        if row is None:
            return True  # Unknown token treated as revoked
        return bool(row["revoked"])

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all active tokens for a user (e.g., on deactivation or role change)."""
        with _connect() as conn:
            cur = conn.execute(
                "UPDATE awi_active_tokens SET revoked=1 WHERE user_id=? AND revoked=0",
                (user_id,),
            )
            conn.commit()
        _audit("tokens_revoked_all", user_id=user_id,
               detail=f"{cur.rowcount} tokens revoked")
        return cur.rowcount

    def unlock_account(self, username: str, admin_user_id: str) -> bool:
        """Admin-initiated manual account unlock."""
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM awi_account_locks WHERE username=? COLLATE NOCASE",
                (username,),
            )
            conn.commit()
        _audit("account_unlocked", username=username,
               detail=f"admin={admin_user_id}")
        return cur.rowcount > 0

    def get_security_audit_log(self, limit: int = 100, event_type: str | None = None,
                               user_id: str | None = None) -> list[dict[str, Any]]:
        with _connect() as conn:
            if event_type and user_id:
                rows = conn.execute(
                    "SELECT * FROM awi_security_audit WHERE event_type=? AND user_id=? "
                    "ORDER BY occurred_at DESC LIMIT ?",
                    (event_type, user_id, limit),
                ).fetchall()
            elif event_type:
                rows = conn.execute(
                    "SELECT * FROM awi_security_audit WHERE event_type=? "
                    "ORDER BY occurred_at DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            elif user_id:
                rows = conn.execute(
                    "SELECT * FROM awi_security_audit WHERE user_id=? "
                    "ORDER BY occurred_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM awi_security_audit ORDER BY occurred_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    # ── First-boot bootstrap ──────────────────────────────────────────────────

    def bootstrap_admin(self, initial_password: str = "AWI@Admin2026!") -> LocalUser:
        """
        Create the default 'admin' superuser if no users exist.
        Called on first application start. Idempotent.
        """
        existing = self.get_user_by_username("admin")
        if existing:
            return existing
        user = self.create_user(
            username="admin",
            display_name="AWI System Administrator",
            email="admin@awi.local",
            role=AWIRole.SYSTEM_ADMIN,
            initial_password=initial_password,
            must_change_pw=True,
        )
        _audit("admin_bootstrapped", username="admin", user_id=user.user_id,
               detail="First-boot admin account created")
        logger.info(
            "AWI: Default admin account created (username='admin'). "
            "Change the password on first login."
        )
        return user

    # ── Token file check utilities ────────────────────────────────────────────

    def verify_token_and_get_user(self, token: str) -> tuple[LocalUser | None, str | None]:
        """
        Decode JWT, check revocation, return (user, error_message).
        Returns (None, error_msg) on any validation failure.
        """
        try:
            payload = decode_token(token)
        except Exception as exc:
            return None, f"Invalid token: {exc}"

        if payload.get("type") != "access":
            return None, "Not an access token."

        jti = payload.get("jti", "")
        if self.is_token_revoked(jti):
            return None, "Token has been revoked."

        user_id = payload.get("sub")
        user = self.get_user_by_id(user_id or "")
        if user is None or not user.is_active:
            return None, "User not found or inactive."

        return user, None

    # ── Private helpers ───────────────────────────────────────────────────────

    def _persist_token(self, jti: str, user_id: str, token_type: str,
                       ttl_minutes: int,
                       ip_address: str | None,
                       user_agent: str | None) -> None:
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(minutes=ttl_minutes)).isoformat()
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO awi_active_tokens "
                "(jti,user_id,token_type,issued_at,expires_at,revoked,ip_address,user_agent) "
                "VALUES (?,?,?,?,?,0,?,?)",
                (jti, user_id, token_type, now.isoformat(), expires, ip_address, user_agent),
            )
            conn.commit()

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> LocalUser:
        return LocalUser(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            email=row["email"],
            role=AWIRole(row["role"]),
            is_active=bool(row["is_active"]),
            must_change_pw=bool(row["must_change_pw"]),
            created_at=row["created_at"],
            last_login=row["last_login"],
        )


# ── Module-level singleton ────────────────────────────────────────────────────

_auth_manager: LocalAuthManager | None = None


def get_auth_manager() -> LocalAuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = LocalAuthManager()
    return _auth_manager
