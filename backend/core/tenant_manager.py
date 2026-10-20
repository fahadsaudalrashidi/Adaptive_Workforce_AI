"""
Tenant Manager — Phase 30C

Enterprise multi-tenant management layer. Extends tenant_isolation.py with
tenant profiles, subscription tiers, usage tracking, and session management.

Design principles:
- All data is local-first: no cloud registry, no external API calls
- Tenant registry persists in SQLite (WAL mode)
- Each tenant has an isolated namespace (via TenantContext from tenant_isolation.py)
- PDPL compliance: no employee data stored in tenant registry — only org metadata
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from .tenant_isolation import (
    TenantContext,
    TenantValidationError,
    validate_tenant_id,
    is_valid_tenant_id,
)

# Phase 34.5 fix: the default db_path used to be a bare relative filename
# ("awi_tenants.db"), which SQLite resolves against the process's current
# working directory — meaning the tenant registry silently ended up in a
# different physical file depending on where the app was launched from
# (e.g. repo root vs. backend/). Anchored to the repo root's data/ directory
# instead, matching the convention already used by local_auth.py, so there
# is exactly one tenant database regardless of CWD.
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DEFAULT_TENANTS_DB_PATH = str(_DATA_DIR / "awi_tenants.db")


# ── Subscription tiers ─────────────────────────────────────────────────────────

class TenantTier(str, Enum):
    STARTER      = "starter"       # SAR 120,000/year — up to 500 employees
    PROFESSIONAL = "professional"  # SAR 360,000/year — up to 2,500 employees
    ENTERPRISE   = "enterprise"    # SAR 720,000/year — up to 10,000 employees
    GOVERNMENT   = "government"    # SAR 960,000/year — unlimited, air-gapped


TIER_LIMITS: dict[TenantTier, dict] = {
    TenantTier.STARTER: {
        "max_employees": 500,
        "max_analyses_per_month": 10,
        "max_report_exports": 20,
        "simulation_scenarios": True,
        "benchmark_access": False,
        "api_access": False,
        "sso": False,
    },
    TenantTier.PROFESSIONAL: {
        "max_employees": 2500,
        "max_analyses_per_month": 50,
        "max_report_exports": 100,
        "simulation_scenarios": True,
        "benchmark_access": True,
        "api_access": False,
        "sso": True,
    },
    TenantTier.ENTERPRISE: {
        "max_employees": 10000,
        "max_analyses_per_month": 200,
        "max_report_exports": 500,
        "simulation_scenarios": True,
        "benchmark_access": True,
        "api_access": True,
        "sso": True,
    },
    TenantTier.GOVERNMENT: {
        "max_employees": -1,           # unlimited
        "max_analyses_per_month": -1,
        "max_report_exports": -1,
        "simulation_scenarios": True,
        "benchmark_access": True,
        "api_access": True,
        "sso": True,
    },
}


# ── Tenant profile ─────────────────────────────────────────────────────────────

@dataclass
class TenantProfile:
    tenant_id: str
    org_name: str
    org_name_ar: str
    tier: TenantTier
    country: str                    # ISO 3166-1 alpha-2
    sector: str                     # e.g. "Healthcare", "Government"
    created_at: str                 # ISO 8601 timestamp
    last_active: str                # ISO 8601 timestamp
    is_active: bool = True
    contact_email: str = ""
    deployment_mode: str = "on_premises"  # on_premises | private_cloud | air_gapped
    language_preference: str = "bilingual"  # en | ar | bilingual
    metadata: dict = field(default_factory=dict)

    @property
    def context(self) -> TenantContext:
        return TenantContext(tenant_id=self.tenant_id)

    @property
    def tier_limits(self) -> dict:
        return TIER_LIMITS[self.tier]

    def can_analyze_employees(self, employee_count: int) -> bool:
        limit = self.tier_limits["max_employees"]
        return limit == -1 or employee_count <= limit

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "org_name": self.org_name,
            "org_name_ar": self.org_name_ar,
            "tier": self.tier.value,
            "country": self.country,
            "sector": self.sector,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "is_active": self.is_active,
            "contact_email": self.contact_email,
            "deployment_mode": self.deployment_mode,
            "language_preference": self.language_preference,
            "tier_limits": self.tier_limits,
        }

    @classmethod
    def from_row(cls, row: dict) -> "TenantProfile":
        metadata = {}
        if row.get("metadata_json"):
            try:
                metadata = json.loads(row["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        return cls(
            tenant_id=row["tenant_id"],
            org_name=row["org_name"],
            org_name_ar=row.get("org_name_ar", ""),
            tier=TenantTier(row.get("tier", TenantTier.PROFESSIONAL.value)),
            country=row.get("country", "SA"),
            sector=row.get("sector", ""),
            created_at=row["created_at"],
            last_active=row.get("last_active", row["created_at"]),
            is_active=bool(row.get("is_active", 1)),
            contact_email=row.get("contact_email", ""),
            deployment_mode=row.get("deployment_mode", "on_premises"),
            language_preference=row.get("language_preference", "bilingual"),
            metadata=metadata,
        )


# ── Session record ─────────────────────────────────────────────────────────────

@dataclass
class TenantSession:
    session_id: str
    tenant_id: str
    started_at: str
    analysis_count: int = 0
    export_count: int = 0
    last_activity: str = ""
    is_active: bool = True

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "started_at": self.started_at,
            "analysis_count": self.analysis_count,
            "export_count": self.export_count,
            "last_activity": self.last_activity,
            "is_active": self.is_active,
        }


# ── Tenant manager ─────────────────────────────────────────────────────────────

class TenantManager:
    """
    Enterprise tenant lifecycle management.

    Manages tenant profiles, sessions, and usage tracking in a local SQLite
    database. Designed for on-premises and air-gapped deployments.
    """

    def __init__(self, db_path: str = _DEFAULT_TENANTS_DB_PATH):
        self._db_path = db_path
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id         TEXT PRIMARY KEY,
                    org_name          TEXT NOT NULL,
                    org_name_ar       TEXT DEFAULT '',
                    tier              TEXT NOT NULL DEFAULT 'professional',
                    country           TEXT NOT NULL DEFAULT 'SA',
                    sector            TEXT DEFAULT '',
                    created_at        TEXT NOT NULL,
                    last_active       TEXT NOT NULL,
                    is_active         INTEGER NOT NULL DEFAULT 1,
                    contact_email     TEXT DEFAULT '',
                    deployment_mode   TEXT DEFAULT 'on_premises',
                    language_preference TEXT DEFAULT 'bilingual',
                    metadata_json     TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS tenant_sessions (
                    session_id        TEXT PRIMARY KEY,
                    tenant_id         TEXT NOT NULL REFERENCES tenants(tenant_id),
                    started_at        TEXT NOT NULL,
                    analysis_count    INTEGER NOT NULL DEFAULT 0,
                    export_count      INTEGER NOT NULL DEFAULT 0,
                    last_activity     TEXT DEFAULT '',
                    is_active         INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS tenant_audit_log (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id         TEXT NOT NULL,
                    session_id        TEXT,
                    event_type        TEXT NOT NULL,
                    event_data        TEXT DEFAULT '{}',
                    occurred_at       TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON tenant_sessions(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_audit_tenant ON tenant_audit_log(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_audit_type ON tenant_audit_log(event_type);
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Tenant CRUD ────────────────────────────────────────────────────────────

    def create_tenant(
        self,
        org_name: str,
        tenant_id: Optional[str] = None,
        org_name_ar: str = "",
        tier: TenantTier = TenantTier.PROFESSIONAL,
        country: str = "SA",
        sector: str = "",
        contact_email: str = "",
        deployment_mode: str = "on_premises",
        language_preference: str = "bilingual",
    ) -> TenantProfile:
        if tenant_id is None:
            slug = org_name.lower().replace(" ", "-")[:20]
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            tenant_id = f"{slug}-{uuid.uuid4().hex[:8]}"
        validate_tenant_id(tenant_id)

        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO tenants
                   (tenant_id, org_name, org_name_ar, tier, country, sector,
                    created_at, last_active, contact_email, deployment_mode, language_preference)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (tenant_id, org_name, org_name_ar, tier.value, country, sector,
                 now, now, contact_email, deployment_mode, language_preference),
            )
            self._log_event(conn, tenant_id, None, "tenant_created", {"org_name": org_name, "tier": tier.value})

        return self.get_tenant(tenant_id)  # type: ignore

    def get_tenant(self, tenant_id: str) -> Optional[TenantProfile]:
        validate_tenant_id(tenant_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
        if row is None:
            return None
        return TenantProfile.from_row(dict(row))

    def list_tenants(self, active_only: bool = True) -> list[TenantProfile]:
        with self._connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM tenants WHERE is_active = 1 ORDER BY org_name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tenants ORDER BY org_name"
                ).fetchall()
        return [TenantProfile.from_row(dict(r)) for r in rows]

    def deactivate_tenant(self, tenant_id: str) -> None:
        validate_tenant_id(tenant_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE tenants SET is_active = 0 WHERE tenant_id = ?", (tenant_id,)
            )
            self._log_event(conn, tenant_id, None, "tenant_deactivated", {})

    def update_last_active(self, tenant_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE tenants SET last_active = ? WHERE tenant_id = ?", (now, tenant_id)
            )

    # ── Session management ─────────────────────────────────────────────────────

    def create_session(self, tenant_id: str) -> TenantSession:
        validate_tenant_id(tenant_id)
        session_id = f"{tenant_id}-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO tenant_sessions (session_id, tenant_id, started_at, last_activity)
                   VALUES (?,?,?,?)""",
                (session_id, tenant_id, now, now),
            )
            self._log_event(conn, tenant_id, session_id, "session_started", {})
        self.update_last_active(tenant_id)
        return TenantSession(
            session_id=session_id,
            tenant_id=tenant_id,
            started_at=now,
            last_activity=now,
        )

    def record_analysis(self, session_id: str, tenant_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE tenant_sessions
                   SET analysis_count = analysis_count + 1, last_activity = ?
                   WHERE session_id = ?""",
                (now, session_id),
            )
            self._log_event(conn, tenant_id, session_id, "analysis_run", {})

    def record_export(self, session_id: str, tenant_id: str, export_type: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE tenant_sessions
                   SET export_count = export_count + 1, last_activity = ?
                   WHERE session_id = ?""",
                (now, session_id),
            )
            self._log_event(conn, tenant_id, session_id, "export_generated", {"type": export_type})

    # ── Audit log ──────────────────────────────────────────────────────────────

    def _log_event(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        session_id: Optional[str],
        event_type: str,
        event_data: dict,
    ) -> None:
        conn.execute(
            """INSERT INTO tenant_audit_log (tenant_id, session_id, event_type, event_data, occurred_at)
               VALUES (?,?,?,?,?)""",
            (tenant_id, session_id, event_type, json.dumps(event_data),
             datetime.now(timezone.utc).isoformat()),
        )

    def get_audit_log(self, tenant_id: str, limit: int = 100) -> list[dict]:
        validate_tenant_id(tenant_id)
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM tenant_audit_log
                   WHERE tenant_id = ?
                   ORDER BY occurred_at DESC
                   LIMIT ?""",
                (tenant_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Usage summary ──────────────────────────────────────────────────────────

    def get_usage_summary(self, tenant_id: str) -> dict:
        validate_tenant_id(tenant_id)
        profile = self.get_tenant(tenant_id)
        if profile is None:
            raise TenantValidationError(f"Tenant not found: {tenant_id!r}")
        with self._connect() as conn:
            agg = conn.execute(
                """SELECT COUNT(*) as session_count,
                          SUM(analysis_count) as total_analyses,
                          SUM(export_count) as total_exports
                   FROM tenant_sessions WHERE tenant_id = ?""",
                (tenant_id,),
            ).fetchone()
        return {
            "tenant_id": tenant_id,
            "org_name": profile.org_name,
            "tier": profile.tier.value,
            "tier_limits": profile.tier_limits,
            "session_count": agg["session_count"] or 0,
            "total_analyses": agg["total_analyses"] or 0,
            "total_exports": agg["total_exports"] or 0,
            "is_active": profile.is_active,
            "last_active": profile.last_active,
        }


# ── Default tenant provision (single-org on-premises deployment) ───────────────

def provision_default_tenant(
    org_name: str = "AWI Enterprise",
    tenant_id: str = "awi-default-org",
    manager: Optional[TenantManager] = None,
) -> TenantProfile:
    """
    Provisions the default single-tenant for on-premises deployments.
    Safe to call repeatedly — idempotent.
    """
    if manager is None:
        manager = TenantManager()
    existing = manager.get_tenant(tenant_id)
    if existing is not None:
        return existing
    return manager.create_tenant(
        org_name=org_name,
        tenant_id=tenant_id,
        tier=TenantTier.ENTERPRISE,
        country="SA",
        deployment_mode="on_premises",
    )
