# Artifact Registry Design — Phase 7

**Document Type:** Infrastructure Design Record  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Design Complete — Persistent Storage Integration Pending  
**Module:** `backend/core/artifact_registry.py`

---

## 1. Purpose

An artifact registry tracks every significant computational output produced by the platform: trained models, uploaded datasets, validation reports, compliance packages. Without a registry, the platform cannot answer: "Where did this model come from?", "Who validated this dataset?", "What training data was used?", or "Is this export approved for release?"

The `ArtifactRegistry` introduced in Phase 7 provides tenant-scoped, sensitivity-classified artifact tracking with cryptographic checksums and mandatory traceability for model artifacts.

---

## 2. Artifact Types

The registry recognizes 10 artifact types, enforced at registration:

| Constant | String | Description |
|----------|--------|-------------|
| `ARTIFACT_MODEL` | `model` | Trained ML model |
| `ARTIFACT_DATASET` | `dataset` | Uploaded or processed dataset |
| `ARTIFACT_REPORT` | `report` | Executive or governance report |
| `ARTIFACT_EXPORT` | `export` | Safe export package |
| `ARTIFACT_VALIDATION` | `validation` | Onboarding validation result |
| `ARTIFACT_AUDIT_LOG` | `audit_log` | Audit trail snapshot |
| `ARTIFACT_ROI_ESTIMATE` | `roi_estimate` | ROI estimation output |
| `ARTIFACT_CALIBRATION` | `calibration` | Calibration curve and metrics |
| `ARTIFACT_SCHEMA_MAP` | `schema_map` | Column mapping result |
| `ARTIFACT_COMPLIANCE` | `compliance` | PDPL or governance compliance record |

An artifact type not in this set raises `ArtifactRegistryError`.

---

## 3. Sensitivity Classification

Every artifact is classified by sensitivity. Default sensitivity is assigned by artifact type:

| Artifact Type | Default Sensitivity | Rationale |
|--------------|--------------------|----|
| `model` | RESTRICTED | Contains learned patterns from employee data |
| `dataset` | RESTRICTED | Raw employee records or aggregates |
| `report` | CONFIDENTIAL | Executive content with aggregate risk bands |
| `export` | CONFIDENTIAL | Has passed safety validator but contains risk data |
| `validation` | INTERNAL | Structural validation results, no personal data |
| `audit_log` | CONFIDENTIAL | Contains operational history |
| `roi_estimate` | INTERNAL | Financial estimates, no personal data |
| `calibration` | INTERNAL | Statistical curves, no personal data |
| `schema_map` | INTERNAL | Column mapping metadata |
| `compliance` | CONFIDENTIAL | PDPL and governance records |

Callers can override the default sensitivity at registration by specifying a higher classification. Downgrading sensitivity below the type default is not enforced in Phase 7 but should be restricted in production.

---

## 4. Retention Policies

Default data retention periods by sensitivity:

| Sensitivity | Default Retention | Rationale |
|-------------|------------------|-----------|
| PUBLIC | 2 years | General availability content |
| INTERNAL | 3 years | Operational records |
| CONFIDENTIAL | 5 years | Regulated HR analytics outputs |
| RESTRICTED | 7 years | Model artifacts with regulatory traceability requirements |

These are defaults only. Tenant-specific data processing agreements or local regulatory requirements may mandate longer or shorter retention periods. The registry records these values for reference — enforcement requires a data lifecycle management system external to this codebase.

---

## 5. `ArtifactRecord` — The Registry Entry

```python
@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str              # UUID, generated at registration
    tenant_id: str                # Owning tenant
    artifact_type: str            # From _VALID_ARTIFACT_TYPES
    name: str                     # Human-readable name
    namespace_path: str           # tenants/{tenant_id}/{type}/{id}
    sensitivity: str              # PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED
    registered_at: str            # ISO-8601 timestamp
    size_bytes: Optional[int]     # None if not measured
    checksum: str                 # SHA-256 of content (hex digest)
    access_policy: str            # Derived from sensitivity
    traceability_reference: str   # Required for model artifacts
    metadata: dict                # Additional context
```

The record is `frozen=True`. Once registered, an artifact record cannot be modified — this preserves audit integrity. Deregistration is a separate operation that removes the record from the in-memory store (production should retain a deletion log).

### 5.1 Checksum

`checksum` is computed via SHA-256 over the artifact name + artifact type + registration timestamp. In a production system with actual file storage, this should be computed over the file content. The current implementation provides a structural placeholder.

### 5.2 Namespace Path

Format: `tenants/{tenant_id}/{artifact_type}/{artifact_id}`

This path is used by `TenantIsolationGuard.assert_path_ownership()` during retrieval. It is the authoritative record of which tenant owns the artifact.

### 5.3 Traceability Reference

Model artifacts (`artifact_type == "model"`) require a non-empty `traceability_reference`. This must contain a reference that allows a reviewer to reconstruct the training context — for example:

- A pipeline run ID (from an ML orchestrator like MLflow, Weights & Biases)
- A Git commit SHA of the training code
- A DVC pipeline hash
- A unique experiment identifier

Attempting to register a model artifact without a traceability reference raises `ArtifactRegistryError`. This is a hard requirement, not a warning.

---

## 6. Registry Operations

### 6.1 `register()`

```python
registry.register(
    tenant_id="acme-corp",
    artifact_type="model",
    name="attrition_model_v3",
    traceability_reference="git:abc1234",
    metadata={"n_employees": 450, "auc": 0.78},
)
```

Returns the `ArtifactRecord`. Raises `ArtifactRegistryError` on:
- Invalid tenant ID
- Invalid artifact type
- Missing traceability reference for model artifacts

### 6.2 `get()`

```python
registry.get(artifact_id="...", requesting_tenant_id="acme-corp")
```

Calls `TenantIsolationGuard.assert_access(artifact.tenant_id)` before returning. Cross-tenant retrieval raises `CrossTenantAccessError`.

Returns `None` if the artifact ID does not exist (not `ArtifactRegistryError`) — absence is not an error.

### 6.3 `list_artifacts()`

Returns all `ArtifactRecord` objects for a given `tenant_id`. Does not require a guard check (the tenant_id parameter is used as the filter). Callers are responsible for ensuring the requesting user has access to that tenant.

---

## 7. Access Policies

Access policy strings by sensitivity:

| Sensitivity | Access Policy |
|-------------|--------------|
| PUBLIC | `read:all` |
| INTERNAL | `read:authenticated` |
| CONFIDENTIAL | `read:authorized-roles` |
| RESTRICTED | `read:admin-only` |

These are metadata strings recorded in the `ArtifactRecord`. They do not directly enforce access in Phase 7 — enforcement requires an authorization middleware layer (not implemented).

---

## 8. Limitations and Production Requirements

### 8.1 Persistent Storage

Current: in-memory `dict` keyed by `artifact_id`. Data is lost on restart. Production requires:
- Artifact metadata stored in PostgreSQL with tenant-partitioned rows
- Actual file content stored in object storage (AWS S3, Azure Blob) with tenant-scoped prefixes
- Content-addressed checksums over actual file bytes (not placeholder)

### 8.2 Checksum Integrity

Current checksum is over a string concatenation of name + type + timestamp. Production requires:
- SHA-256 over the actual artifact file bytes
- Checksum stored before the file is moved to its final location
- Periodic re-verification of stored checksums against object storage

### 8.3 Retention Enforcement

Retention periods are recorded but not enforced. Production requires:
- A scheduled job that expires artifacts past their retention date
- Soft-delete before hard-delete (audit log of deletion)
- Tenant notification before deletion for PDPL compliance

### 8.4 Versioning

Not implemented. Production model artifacts should be versioned, with the active version tracked separately from historical versions.

---

## 9. Test Verification Summary

Tests in `tests/test_phase7_tenant_isolation.py::TestArtifactRegistry`:

| Test | Verifies |
|------|---------|
| `test_artifact_registration_succeeds` | Clean registration returns ArtifactRecord |
| `test_artifact_record_is_frozen` | Frozen record cannot be mutated |
| `test_artifact_type_validation` | Invalid type raises ArtifactRegistryError |
| `test_model_requires_traceability` | Model without reference raises ArtifactRegistryError |
| `test_model_with_traceability_succeeds` | Model with reference registers successfully |
| `test_artifact_sensitivity_defaults` | Default sensitivities match design |
| `test_artifact_namespace_path` | Path follows `tenants/{id}/{type}/{id}` format |
| `test_artifact_retrieval` | Registered artifact retrievable by ID |
| `test_cross_tenant_artifact_access_blocked` | Cross-tenant get raises CrossTenantAccessError |
| `test_artifact_list_by_tenant` | List returns only that tenant's artifacts |
| `test_artifact_checksum_present` | Checksum is non-empty string |
| `test_artifact_retention_recorded` | Retention period in metadata |

All 12 tests pass as of 2026-05-20.

---

*The artifact registry is the platform's memory of what was computed, when, and for whom. Traceability requirements for model artifacts are non-negotiable — an untraced model cannot be audited, retracted, or reproduced. The current in-memory implementation must be replaced with persistent, tamper-evident storage before any regulatory review.*
