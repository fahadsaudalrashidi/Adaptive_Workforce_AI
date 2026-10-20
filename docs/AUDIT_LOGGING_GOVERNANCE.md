# Audit Logging Governance — Phase 7

**Document Type:** Audit & Compliance Architecture Record  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Implementation Complete — Pending Persistent Storage Integration  
**Module:** `backend/core/audit_logger.py`

---

## 1. Purpose

Audit logging is not optional in HR analytics systems. When workforce risk scores influence organizational decisions, the platform must maintain an immutable, queryable trail of: who requested what, when, for which tenant, and what the system produced. This document records the audit logging architecture, the PII protection guarantees embedded in the logger, the 18 event types covered, and the limitations that must be resolved before production deployment.

---

## 2. Design Principles

### 2.1 No Raw Employee Data in Audit Logs

The most important design constraint: `AuditLogEntry` has no field that can hold a DataFrame, individual employee record, or individual risk score. This is architectural, not enforced by validation:

```python
@dataclass(frozen=True)
class AuditLogEntry:
    entry_id: str
    tenant_id: str
    event_type: str
    actor_id: str
    timestamp: str
    summary: str          # Free text — PII-checked before storage
    severity: str
    module: str
    metadata: dict        # Stripped of DataFrame keys before storage
    session_id: Optional[str]
```

There is no `raw_data`, `employee_records`, `y_prob_series`, or `dataframe` field. An audit entry that needed to hold employee-level data could not be constructed because the type does not support it.

### 2.2 PII Protection in Summary Text

The `summary` field is free text. It is checked by `_assert_no_pii_in_summary()` before any entry is stored. This check looks for known PII indicators:

- `national id`, `national_id`
- `iqama`
- `رقم الهوية`, `رقم_الهوية` (Arabic national ID)
- `رقم الإقامة` (Arabic residency number)
- `passport`
- `iban`
- IBAN-like patterns (`sa\d{2}[a-z0-9]{18}`)
- `employee record:`
- `raw data:`
- `monthly income:`
- `salary:`

If any indicator is found, `AuditLogViolation(ValueError)` is raised. The entry is not stored.

### 2.3 Metadata Stripping

The `metadata` field accepts arbitrary `dict` payloads. Before storage, the logger strips keys that commonly carry raw employee data:

- `df`, `dataframe`
- `raw_data`
- `employee_data`
- `y_prob`, `y_true`

These keys are removed from the metadata dict. The remaining metadata (counts, configuration, status codes, etc.) is stored.

### 2.4 Tenant Isolation in Log Reads

`get_entries(requesting_tenant_id, target_tenant_id)` enforces that the requesting tenant can only retrieve their own entries:

```python
if requesting_tenant_id != target_tenant_id:
    raise AuditLogViolation("Cross-tenant audit log access denied.")
```

This ensures that Tenant A cannot retrieve Tenant B's audit history even if both are authenticated.

---

## 3. Event Type Inventory

The 18 registered event types cover the full lifecycle of a tenant's data on the platform:

| Event Type Constant | Event String | Triggered By |
|---------------------|-------------|--------------|
| `EVT_TENANT_CREATED` | `tenant_created` | Tenant provisioning |
| `EVT_DATASET_UPLOADED` | `dataset_uploaded` | Dataset upload endpoint |
| `EVT_DATASET_VALIDATED` | `dataset_validated` | Onboarding pipeline completion |
| `EVT_DATASET_REJECTED` | `dataset_rejected` | Onboarding pipeline failure |
| `EVT_MODEL_TRAINED` | `model_trained` | Model training completion |
| `EVT_MODEL_DEPLOYED` | `model_deployed` | Model activation |
| `EVT_MODEL_RETRAINED` | `model_retrained` | Model refresh |
| `EVT_MODEL_RETIRED` | `model_retired` | Model decommissioning |
| `EVT_REPORT_GENERATED` | `report_generated` | Executive report endpoint |
| `EVT_EXPORT_REQUESTED` | `export_requested` | Export endpoint |
| `EVT_EXPORT_COMPLETED` | `export_completed` | Export packaging |
| `EVT_EXPORT_BLOCKED` | `export_blocked` | ExportSafetyValidator block |
| `EVT_ONBOARDING_COMPLETED` | `onboarding_completed` | All 7 pipeline stages passed |
| `EVT_ONBOARDING_FAILED` | `onboarding_failed` | Any pipeline stage blocked |
| `EVT_PII_DETECTED` | `pii_detected` | PII found in dataset or export |
| `EVT_GOVERNANCE_VIOLATION` | `governance_violation` | Language or policy violation |
| `EVT_SETTINGS_CHANGED` | `settings_changed` | Tenant settings update |
| `EVT_ACCESS_DENIED` | `access_denied` | Cross-tenant guard rejection |

An event type not in this set raises `AuditLogViolation`. Unknown events cannot be silently logged.

---

## 4. Severity Levels

Each audit entry carries a `severity` field. Severity must be one of:

| Level | Usage |
|-------|-------|
| `INFO` | Normal operation events (uploads, reports, exports) |
| `WARNING` | PII detected and stripped, governance corrections applied |
| `ERROR` | Rejected datasets, blocked exports, failed onboarding |
| `CRITICAL` | Cross-tenant access denied, governance violations, security incidents |

---

## 5. `AuditLogEntry` Immutability

`AuditLogEntry` is a `frozen=True` dataclass. Once created:
- No field can be modified
- No field can be added
- The object is hashable and can be stored in sets

This prevents post-hoc tampering with audit records in the in-memory store. In a persistent store, the equivalent guarantee must come from database-level immutability (write-once rows, no UPDATE/DELETE permissions on audit tables).

---

## 6. Module-Level Singleton

`get_default_logger()` returns a module-level `AuditLogger` singleton. This is correct for single-process deployments (development, single-worker containers). Production deployments with multiple workers require a shared persistent store; each worker's in-memory singleton would be isolated, leading to incomplete audit trails.

The `log_event()` convenience function delegates to the singleton and should be used in all application code for simplicity.

---

## 7. Limitations and Required Upgrades

### 7.1 In-Memory Store

Current: entries stored in `self._store: list[AuditLogEntry]`.

Production requirement: persistent write-once audit table in PostgreSQL (or equivalent) with:
- Append-only access for the application role (no DELETE, no UPDATE)
- Cryptographic hash chain or equivalent tamper evidence
- Index on `(tenant_id, timestamp)` for efficient retrieval

### 7.2 Log Rotation and Retention

Not implemented in Phase 7. Production requires:
- Configurable retention period per event type (recommended: minimum 7 years for HR compliance)
- Archival to cold storage after active retention period
- Audit log export for regulatory requests (PDPL Article 18 data subject requests)

### 7.3 Real-Time Alerting

Not implemented. Production should include:
- Alert on `EVT_ACCESS_DENIED` (possible tenant isolation breach attempt)
- Alert on `EVT_GOVERNANCE_VIOLATION` (possible policy bypass attempt)
- Alert on `EVT_EXPORT_BLOCKED` frequency anomaly

---

## 8. PDPL Compliance Relevance

Under Saudi PDPL (Royal Decree M/19), data controllers must maintain records of processing activities. The audit log is the platform's primary record of:

- Which datasets were processed for which tenant
- Which reports were generated
- Which exports were requested
- Which PII incidents occurred

However: **the audit log is a technical control, not a legal compliance certification.** A qualified legal team must review whether the current logging scope satisfies PDPL Article 31 (records of processing) requirements for the specific tenant's use case.

---

## 9. Test Verification Summary

Tests in `tests/test_phase7_tenant_isolation.py::TestAuditLogger`:

| Test | Verifies |
|------|---------|
| `test_audit_logger_records_event` | Event stored and retrievable |
| `test_audit_logger_rejects_invalid_event_type` | Unknown events raise AuditLogViolation |
| `test_audit_logger_rejects_invalid_tenant_id` | Invalid tenant raises AuditLogViolation |
| `test_audit_logger_never_stores_raw_employee_data` | DataFrame key stripped from metadata |
| `test_pii_in_summary_is_rejected` | PII summary raises AuditLogViolation |
| `test_cross_tenant_log_access_raises` | Cross-tenant read raises AuditLogViolation |
| `test_audit_log_entry_is_frozen` | Mutation of frozen entry raises FrozenInstanceError |
| `test_severity_levels_accepted` | INFO/WARNING/ERROR/CRITICAL all accepted |
| `test_audit_log_singleton` | get_default_logger() returns same instance |

All 9 tests pass as of 2026-05-20.

---

*Audit logging provides governance accountability. The in-memory implementation is sufficient for Phase 7 scaffolding. Persistent, tamper-evident audit storage must be implemented before any live customer deployment where regulatory traceability is required.*
