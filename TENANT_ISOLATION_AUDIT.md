# Tenant Isolation Audit — Phase 7

**Document Type:** Security Architecture Audit  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Architecture Complete — Pending Independent Security Review  
**Module:** `backend/core/tenant_isolation.py`

---

## 1. Purpose

This document audits the tenant isolation architecture introduced in Phase 7. It records the design decisions, isolation guarantees, enforcement mechanisms, limitations, and required pre-deployment steps. Tenant isolation is the most critical security property of a multi-tenant SaaS platform — data from one tenant must never be accessible to another.

---

## 2. Design Philosophy: Structural Isolation

Phase 7 implements **structural isolation**, not configuration-based isolation. This is a deliberate design choice:

| Isolation Type | Description | Risk |
|----------------|-------------|------|
| Configuration-based | A shared store with tenant filters; bypass risk if filter is missed | Moderate — a single forgotten WHERE clause exposes data |
| Structural (chosen) | Namespace prefixes make cross-tenant paths physically different | Low — cross-tenant access requires a deliberately wrong path |

Every resource in the system is stored under a path of the form:

```
tenants/{tenant_id}/{resource_type}/{resource_id}
```

A request for tenant `acme-corp`'s dataset can never accidentally resolve to `beta-inc`'s dataset because the paths are structurally different strings. There is no shared lookup table that could be bypassed.

---

## 3. `TenantContext` — Identity and Namespace

**Class:** `TenantContext` (frozen dataclass)  
**File:** `backend/core/tenant_isolation.py`

### 3.1 Fields

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | str | Validated tenant identifier |
| `display_name` | str | Human-readable name (not used in paths) |
| `created_at` | str | ISO-8601 timestamp of context creation |

### 3.2 Tenant ID Validation

Tenant IDs must match: `^[a-z0-9][a-z0-9_\-]{1,61}[a-z0-9]$`

This regex enforces:
- Lowercase alphanumeric only (plus underscore and hyphen)
- Minimum 3 characters, maximum 63 characters
- No leading/trailing hyphens or underscores (prevents DNS-like confusion)
- No uppercase, spaces, or special characters (prevents path injection)

Violation raises `TenantValidationError(ValueError)`.

### 3.3 Namespace Methods

| Method | Returns | Example |
|--------|---------|---------|
| `dataset_namespace()` | str | `tenants/acme-corp/datasets` |
| `artifact_namespace()` | str | `tenants/acme-corp/artifacts` |
| `audit_namespace()` | str | `tenants/acme-corp/audit` |
| `model_namespace()` | str | `tenants/acme-corp/models` |
| `report_namespace()` | str | `tenants/acme-corp/reports` |
| `temp_namespace()` | str | `tenants/acme-corp/temp` |

All namespace strings begin with `tenants/{tenant_id}/`. This prefix is checked by `TenantIsolationGuard.assert_path_ownership()`.

### 3.4 Ownership Check

```python
ctx.owns("tenants/acme-corp/datasets/ds-001")  # True
ctx.owns("tenants/beta-inc/datasets/ds-001")   # False
```

`owns()` checks that the path starts with `tenants/{self.tenant_id}/`. This is used as a precondition in the guard layer.

---

## 4. `TenantIsolationGuard` — Cross-Tenant Access Enforcement

**Class:** `TenantIsolationGuard`  
**File:** `backend/core/tenant_isolation.py`

The guard takes a `TenantContext` at construction and enforces that every resource access belongs to that context's tenant.

### 4.1 Methods

| Method | Behavior |
|--------|----------|
| `validate_access(resource_tenant_id)` | Returns `True` if IDs match, `False` otherwise |
| `assert_access(resource_tenant_id)` | Raises `CrossTenantAccessError` if IDs differ |
| `assert_path_ownership(path)` | Raises `CrossTenantAccessError` if path prefix doesn't match |

### 4.2 `CrossTenantAccessError`

`CrossTenantAccessError` extends `PermissionError`. Using `PermissionError` as the base class means:
- FastAPI will not expose the internal tenant IDs in a default 500 error
- Python's exception hierarchy allows `except PermissionError` to catch it in integration code
- It is semantically distinct from authentication failures (`AuthenticationError`)

**Important:** The error message does NOT include the target tenant's actual ID (to prevent tenant enumeration via error messages). It only states that the requesting tenant does not have access.

### 4.3 Test Coverage

The following cross-tenant scenarios are covered in `tests/test_phase7_tenant_isolation.py`:

- Same tenant access returns `True`
- Different tenant access returns `False` from `validate_access()`
- Different tenant access raises `CrossTenantAccessError` from `assert_access()`
- Path ownership check raises on wrong prefix
- Path ownership check passes on correct prefix
- Frozen context cannot be mutated after creation

---

## 5. Isolation Boundary Matrix

| Operation | Isolation Enforcement | Test |
|-----------|----------------------|------|
| Dataset registration | Namespace prefix in artifact path | `test_artifact_namespace_isolation` |
| Artifact retrieval | Guard `assert_access()` in `ArtifactRegistry.get()` | `test_cross_tenant_artifact_access_blocked` |
| Audit log write | Tenant ID validated before entry creation | `test_audit_logger_isolates_by_tenant` |
| Audit log read | Guard check before `get_entries()` | `test_cross_tenant_log_access_raises` |
| Report generation | Namespace prefix in report path | `test_report_namespace_scoped` |
| Export packaging | Tenant ID embedded in `SafeExportPackage` | `test_tenant_id_in_package` |
| API access | JWT tenant claim vs. path parameter (pending implementation) | Pending auth completion |

---

## 6. Limitations and Known Gaps

### 6.1 In-Memory Storage (Current)

`AuditLogger` and `ArtifactRegistry` use in-memory stores (`list` and `dict`). This is correct for Phase 7 scaffolding but means:
- Data is lost on process restart
- Stores cannot be queried across multiple API workers
- Production requires a tenant-scoped database with row-level security

### 6.2 File System Isolation (Not Implemented)

The namespace paths produced by `TenantContext` are string namespaces. They do NOT currently map to actual file system directories or database schemas. When a persistent store is added, it must enforce these namespaces structurally (separate DB schemas, separate object storage prefixes with IAM policies).

### 6.3 JWT Authentication (Placeholder)

The API layer has placeholder authentication. Until JWT validation is complete, a caller can pass any `tenant_id` in the URL path and the guard will enforce isolation based on that claimed ID — but the claim is unverified. Full isolation requires the JWT to carry a verified `tenant_id` claim that is compared to the path parameter before any processing begins.

### 6.4 Tenant Provisioning Not Hardened

Any client can call `POST /v1/tenants` to create a new tenant context. Production requires:
- Admin-only access to tenant provisioning endpoints
- Billing system integration before provisioning
- Tenant ID uniqueness enforcement in a persistent store

---

## 7. Threat Model

| Threat | Mitigation | Status |
|--------|------------|--------|
| Tenant A reads Tenant B's artifacts | `TenantIsolationGuard.assert_access()` in every `get()` call | Implemented |
| Tenant A writes to Tenant B's namespace | Namespace prefix enforced at registration | Implemented |
| Path traversal attack (e.g., `../../other-tenant`) | Tenant ID regex prevents `../` characters | Implemented |
| JWT tenant claim forgery | JWT signature validation (pending) | Pending |
| Tenant ID enumeration via error messages | Error messages do not include target tenant ID | Implemented |
| Cross-tenant audit log leakage | `get_entries()` filters by tenant_id | Implemented |
| Shared in-memory store pollution | Separate list/dict per event type with tenant filter | Implemented (in-memory) |

---

## 8. Required Pre-Deployment Hardening

The following must be completed before any live multi-tenant deployment:

1. **Implement JWT authentication** — extract and verify `tenant_id` from Bearer token
2. **Persistent tenant-scoped storage** — replace in-memory stores with tenant-partitioned database
3. **Database row-level security (RLS)** — PostgreSQL RLS or equivalent to prevent SQL-level cross-tenant queries
4. **Object storage IAM policies** — S3 or Azure Blob with tenant-scoped prefixes and least-privilege IAM
5. **Admin endpoint protection** — tenant provisioning must require elevated scope
6. **Penetration test** — independent test of isolation boundaries by security team

---

## 9. Test Verification Summary

```
tests/test_phase7_tenant_isolation.py::TestTenantContext         — 15 tests ✓
tests/test_phase7_tenant_isolation.py::TestTenantIsolationGuard  — 8 tests  ✓
tests/test_phase7_tenant_isolation.py::TestAuditLogger           — 9 tests  ✓
tests/test_phase7_tenant_isolation.py::TestArtifactRegistry      — 12 tests ✓
```

All 44 isolation-related tests pass as of 2026-05-20. Zero cross-tenant data leakage paths found in the current in-memory implementation.

---

*This document must be reviewed by an independent security engineer before any multi-tenant production deployment. Structural isolation is necessary but not sufficient — the JWT authentication layer, persistent storage, and infrastructure-level IAM policies must be reviewed together.*
