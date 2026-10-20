# AWI Multi-Tenant Foundation
## Enterprise Workforce Intelligence Platform — Phase 30C

**Version:** v2.0.0-enterprise  
**Date:** 2026-06-01  
**Status:** Foundation Complete — Production-Ready for Single-Tenant and Multi-Tenant On-Premises

---

## Architecture Overview

AWI's multi-tenant architecture is built for **data sovereignty first**. Every design decision ensures that:
- No employee data crosses tenant boundaries
- All data remains on-premises (no cloud registry)
- PDPL Article 6 compliance is structurally enforced, not policy-based
- The same codebase serves single-tenant (most deployments) and multi-tenant (government, holding company) configurations

---

## Layer 1 — Tenant Isolation (`tenant_isolation.py`)

The foundational isolation layer. All artifact paths, audit logs, and report storage are namespaced under `tenants/{tenant_id}/...`.

### Key Components

| Component | Purpose |
|---|---|
| `TenantContext` | Immutable tenant session context. Generates all namespace paths. |
| `TenantIsolationGuard` | Hard access validation. Raises `CrossTenantAccessError` on any cross-tenant attempt. |
| `validate_tenant_id()` | Enforces slug pattern: `[a-z0-9][a-z0-9_\-]{1,61}[a-z0-9]` |

### Namespace Structure

```
tenants/
└── {tenant_id}/
    ├── datasets/           ← raw data, cleared per session
    ├── artifacts/
    │   ├── executive_report/
    │   ├── governance_report/
    │   ├── calibration_report/
    │   └── audit_package/
    ├── reports/            ← generated PDFs and HTML
    ├── models/             ← per-tenant ML artifacts (future)
    ├── audit/              ← immutable audit trail
    └── tmp/                ← cleared after each operation
```

### Cross-Tenant Access Prevention

```python
guard = TenantIsolationGuard()
guard.assert_access("tenant-a", "tenant-b", "workforce report")
# → raises CrossTenantAccessError
```

---

## Layer 2 — Tenant Manager (`tenant_manager.py`) — Phase 30C

Enterprise lifecycle management layer. Extends tenant isolation with:
- Tenant profiles + subscription tiers
- Session tracking and usage metrics  
- Audit event log
- SQLite-persisted registry (WAL mode, local-only)

### Subscription Tiers

| Tier | Annual (SAR) | Max Employees | Benchmark | API | SSO |
|---|---|---|---|---|---|
| **Starter** | 120,000 | 500 | — | — | — |
| **Professional** | 360,000 | 2,500 | ✓ | — | ✓ |
| **Enterprise** | 720,000 | 10,000 | ✓ | ✓ | ✓ |
| **Government** | 960,000 | Unlimited | ✓ | ✓ | ✓ |

### Tenant Lifecycle

```python
from backend.core.tenant_manager import TenantManager, TenantTier

manager = TenantManager(db_path="awi_tenants.db")

# Create tenant
profile = manager.create_tenant(
    org_name="Saudi National Bank",
    tier=TenantTier.ENTERPRISE,
    country="SA",
    sector="Banking",
)

# Start analysis session
session = manager.create_session(profile.tenant_id)

# Record events
manager.record_analysis(session.session_id, profile.tenant_id)
manager.record_export(session.session_id, profile.tenant_id, "board_report_v3")

# Usage summary
summary = manager.get_usage_summary(profile.tenant_id)
```

### Database Schema

```sql
tenants (
    tenant_id         TEXT PRIMARY KEY,    -- slug: e.g. "snb-sa-prod"
    org_name          TEXT NOT NULL,       -- display name
    org_name_ar       TEXT,                -- Arabic name
    tier              TEXT NOT NULL,       -- starter|professional|enterprise|government
    country           TEXT NOT NULL,       -- ISO 3166-1: SA, AE, QA, KW, BH, OM
    sector            TEXT,                -- industry classification
    created_at        TEXT,                -- ISO 8601
    last_active       TEXT,                -- ISO 8601
    is_active         INTEGER,             -- 1 = active
    deployment_mode   TEXT,                -- on_premises|private_cloud|air_gapped
    language_preference TEXT              -- en|ar|bilingual
)

tenant_sessions (
    session_id        TEXT PRIMARY KEY,   -- {tenant_id}-{uuid8}
    tenant_id         TEXT NOT NULL REFERENCES tenants,
    started_at        TEXT NOT NULL,
    analysis_count    INTEGER DEFAULT 0,
    export_count      INTEGER DEFAULT 0,
    last_activity     TEXT,
    is_active         INTEGER DEFAULT 1
)

tenant_audit_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT NOT NULL,
    session_id        TEXT,
    event_type        TEXT NOT NULL,     -- tenant_created|session_started|analysis_run|export_generated
    event_data        TEXT,              -- JSON
    occurred_at       TEXT NOT NULL
)
```

---

## Deployment Patterns

### Pattern 1 — Single-Tenant On-Premises (Default)

Most deployments. One organisation, one AWI instance, one tenant_id.

```python
from backend.core.tenant_manager import provision_default_tenant

profile = provision_default_tenant(
    org_name="Saudi Aramco — HR Analytics",
    tenant_id="aramco-hr-prod",
)
```

All API calls use this single tenant_id. No multi-tenant complexity exposed to end users.

### Pattern 2 — Government Multi-Instance

A Saudi government ministry operating multiple agencies on one AWI server. Each agency is a tenant with strict isolation.

```
Ministry of HR AWI Instance
├── tenant: mol-riyadh       (Ministry of Labour — Riyadh Region)
├── tenant: mol-jeddah       (Ministry of Labour — Jeddah Region)
└── tenant: mol-eastern      (Ministry of Labour — Eastern Province)
```

Each agency's workforce data, reports, and audit trail are completely isolated from the others.

### Pattern 3 — Holding Company Multi-Tenant

A Saudi holding company managing multiple subsidiaries.

```
AWI for Saudi Holdings Group
├── tenant: subsidiary-a     (Healthcare division)
├── tenant: subsidiary-b     (Real estate division)
└── tenant: subsidiary-c     (Technology division)
```

Group-level dashboard aggregates risk indices (anonymised) without sharing individual employee data across tenants.

---

## PDPL Compliance Notes

1. **Employee records never stored in tenant registry**: `tenants` and `tenant_sessions` tables contain only organizational metadata (name, tier, sector) — zero employee data.
2. **Tenant isolation prevents cross-subsidiary data access**: A holding company cannot access Subsidiary A's employee records through Subsidiary B's session.
3. **Audit trail per tenant**: `tenant_audit_log` provides a per-tenant event trace for PDPL accountability obligations.
4. **Data deleted on session end**: Workforce analysis data (SQLite result_json) is session-scoped and never persists beyond the analysis session lifecycle.

---

## Phase 30C Implementation Files

| File | Description |
|---|---|
| `backend/core/tenant_isolation.py` | Foundation isolation layer (Phase 7, unchanged) |
| `backend/core/tenant_manager.py` | Enterprise lifecycle management (Phase 30C, new) |
| `MULTITENANT_FOUNDATION.md` | This document |

---

## Phase 31 Extensions (Roadmap)

- **RBAC (Role-Based Access Control)**: CHRO, HR Manager, HR Analyst, Read-Only roles per tenant
- **Group aggregation view**: Cross-tenant risk index aggregation with k-anonymity (min group size 5)
- **Tenant-level ML calibration**: Per-tenant threshold tuning and model drift detection
- **Tenant onboarding wizard**: UI flow for provisioning new tenants from the admin panel
- **API key management**: Per-tenant API keys with rate limiting and audit

---

*AWI Multi-Tenant Foundation — Phase 30C | 2026-06-01*
