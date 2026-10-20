# Production API Surface — Phase 7 Audit

**Document Type:** API Design & Governance Audit  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Design Complete — Pending Security Review Before Live Deployment  
**Reviewer Required:** Security Engineer, Platform Architect

---

## 1. Purpose

This document audits the `backend/api/enterprise_routes.py` API surface introduced in Phase 7. It records the endpoint inventory, request/response contracts, governance controls embedded in every response, and the access control and rate-limiting requirements that must be enforced before any customer-facing deployment.

---

## 2. API Overview

| Attribute | Value |
|-----------|-------|
| Framework | FastAPI (Starlette ASGI) |
| Router prefix | `/v1` |
| Tag | `enterprise` |
| Auth strategy | Placeholder JWT (production: Bearer token with tenant claim) |
| Response envelope | All responses include `GovernanceStatus` |
| Employee-level data in responses | **Never** — architecturally excluded |

The router is registered at `backend/api/enterprise_routes.py` and must be mounted on the FastAPI application instance in `backend/api/main.py`.

---

## 3. Endpoint Inventory

### 3.1 Tenant Management (`/v1/tenants`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/tenants` | Provision a new tenant context |
| GET | `/v1/tenants/{tenant_id}` | Retrieve tenant metadata |
| GET | `/v1/tenants/{tenant_id}/status` | Health and readiness status |
| PUT | `/v1/tenants/{tenant_id}/settings` | Update tenant settings |

**Governance notes:**
- Tenant creation writes an `EVT_TENANT_CREATED` audit log entry via AuditLogger.
- Tenant ID is validated against the `^[a-z0-9][a-z0-9_\-]{1,61}[a-z0-9]$` pattern before any resource allocation.
- Settings updates write `EVT_SETTINGS_CHANGED` audit entries.

### 3.2 Dataset Onboarding (`/v1/tenants/{tenant_id}/datasets`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/tenants/{tenant_id}/datasets/upload` | Upload and validate a dataset |
| GET | `/v1/tenants/{tenant_id}/datasets` | List registered datasets |
| GET | `/v1/tenants/{tenant_id}/datasets/{dataset_id}` | Dataset metadata and validation status |
| DELETE | `/v1/tenants/{tenant_id}/datasets/{dataset_id}` | Remove a dataset |

**Governance notes:**
- Upload runs `EnterpriseOnboardingPipeline` (7 stages) before registering the artifact.
- Only `.csv`, `.xlsx`, `.xls`, `.parquet` files are accepted (enforced in `production_settings.py`).
- Files are stored in tenant-scoped namespace paths: `tenants/{tenant_id}/datasets/{dataset_id}`.
- Onboarding completion writes `EVT_DATASET_UPLOADED` and `EVT_ONBOARDING_COMPLETED` audit entries.

### 3.3 Model Training (`/v1/tenants/{tenant_id}/models`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/tenants/{tenant_id}/models/train` | Initiate a training job |
| GET | `/v1/tenants/{tenant_id}/models` | List trained models |
| GET | `/v1/tenants/{tenant_id}/models/{model_id}` | Model metadata and traceability |
| DELETE | `/v1/tenants/{tenant_id}/models/{model_id}` | Deregister a model |

**Governance notes:**
- Every model registered in the ArtifactRegistry requires a `traceability_reference` (e.g., pipeline run ID, Git commit SHA).
- Model artifacts are classified `RESTRICTED` by default (7-year retention).
- Training job writes `EVT_MODEL_TRAINED` audit entry.

### 3.4 Reporting (`/v1/tenants/{tenant_id}/reports`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/tenants/{tenant_id}/reports/executive` | Generate an executive-level report |
| GET | `/v1/tenants/{tenant_id}/reports` | List generated reports |
| GET | `/v1/tenants/{tenant_id}/reports/{report_id}` | Retrieve a report |

**Governance notes:**
- `ExecutiveReportResponse` is explicitly defined with NO fields for `y_prob`, `individual_risk_score`, `employee_id`, or `employee_number`.
- All report payloads pass through `ExportSafetyValidator` before return.
- Report generation writes `EVT_REPORT_GENERATED` audit entry.

### 3.5 Export (`/v1/tenants/{tenant_id}/exports`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/tenants/{tenant_id}/exports` | Request a safe export package |
| GET | `/v1/tenants/{tenant_id}/exports/{export_id}` | Retrieve a completed export |

**Governance notes:**
- Every export passes through `ExportSafetyValidator.validate_and_sanitize()`.
- Export response always includes `governance_disclaimer`, `confidence_warning`, and `pdpl_note`.
- Export request writes `EVT_EXPORT_REQUESTED` audit entry.

---

## 4. `GovernanceStatus` Response Model

Every response model includes a `governance_status` field of type `GovernanceStatus`. This is a non-optional Pydantic model:

```python
class GovernanceStatus(BaseModel):
    status: str          # "OK" | "WARNING" | "BLOCKED"
    disclaimer: str      # Governance disclaimer text
    pdpl_note: str       # PDPL review note text
```

This field is architecturally required — routes that omit it fail the governance contract. The API layer must not return raw dict responses without this wrapper.

---

## 5. Response Field Exclusions (Employee-Level Data)

The `ExecutiveReportResponse` Pydantic model is deliberately constructed with NO fields for:

- `y_prob` — individual attrition probability
- `individual_risk_score` — per-employee score
- `employee_id` — direct employee identifier
- `employee_number` — HR system employee number
- `predicted_probability` — individual prediction
- `attrition_probability` — individual prediction alias

These fields cannot be added to the response model without a deliberate architectural change. They are excluded at the type level, not by filtering.

---

## 6. Authentication Architecture (Placeholder — Must Be Completed)

Phase 7 includes placeholder authentication stubs. **The following must be implemented before any live customer deployment:**

| Requirement | Status |
|-------------|--------|
| JWT Bearer token validation | Placeholder — implement with python-jose or equivalent |
| Tenant claim extraction from JWT payload | Placeholder — must match `tenant_id` path parameter |
| Cross-tenant JWT rejection | Placeholder — `TenantIsolationGuard.assert_access()` enforces after extraction |
| Token expiry enforcement | Placeholder — JWT library handles |
| Admin vs. read-only scopes | Not implemented in Phase 7 |
| Rate limiting per tenant | Not implemented in Phase 7 |

**CRITICAL:** Do not deploy to live customers until JWT validation is complete. The placeholder stubs accept any tenant ID.

---

## 7. Rate Limiting and Abuse Prevention (Not Implemented — Required for Production)

Phase 7 scaffolds the API structure only. The following must be added before customer deployment:

- Per-tenant request rate limiting (recommended: slowapi or similar)
- Dataset upload size limits (recommended: ≤50 MB per upload)
- Concurrent training job limits per tenant
- Report generation throttling for large tenant populations

---

## 8. Error Response Contract

All error responses must follow the standard FastAPI `HTTPException` pattern with:
- `status_code`: HTTP status code
- `detail`: Human-readable error message (no PII, no stack traces)
- Governance status is not attached to error responses (not required)

---

## 9. Audit Trail Requirements

Every state-changing endpoint writes to the AuditLogger before returning a response. The event types mapped to endpoints are:

| Endpoint | Event Type |
|----------|------------|
| POST /tenants | `EVT_TENANT_CREATED` |
| PUT /tenants/{id}/settings | `EVT_SETTINGS_CHANGED` |
| POST /datasets/upload | `EVT_DATASET_UPLOADED` + `EVT_ONBOARDING_COMPLETED` |
| POST /models/train | `EVT_MODEL_TRAINED` |
| POST /reports/executive | `EVT_REPORT_GENERATED` |
| POST /exports | `EVT_EXPORT_REQUESTED` |

---

## 10. Known Limitations and Open Items

| Item | Severity | Notes |
|------|----------|-------|
| JWT authentication is a placeholder | CRITICAL | Must be implemented before live deployment |
| Rate limiting not implemented | HIGH | Required for multi-tenant fairness and abuse prevention |
| Training jobs are synchronous | MEDIUM | Production requires async job queue (Celery/Redis) |
| Export storage not implemented | MEDIUM | Exports are returned inline; production needs object storage |
| Admin endpoints missing | LOW | Tenant deprovisioning, audit log retrieval, compliance reporting |
| OpenAPI schema not hardened | LOW | Sensitive field descriptions should be reviewed |

---

## 11. Compliance Checklist

- [x] All responses include `governance_status`
- [x] Employee-level fields excluded from response models by type
- [x] Audit events logged for all state-changing operations
- [x] PII fields cannot be returned (ExportSafetyValidator is the final gate)
- [x] Tenant namespace isolation enforced via TenantIsolationGuard
- [x] PDPL note attached to all export responses
- [ ] JWT authentication implemented (placeholder — pending)
- [ ] Rate limiting implemented (pending)
- [ ] Security penetration test completed (pending)
- [ ] PDPL Data Processing Impact Assessment (DPIA) completed (pending legal)

---

*This document records the designed API surface. The implementation in `backend/api/enterprise_routes.py` is the authoritative contract. Any deviation must be reviewed by the platform architect.*
