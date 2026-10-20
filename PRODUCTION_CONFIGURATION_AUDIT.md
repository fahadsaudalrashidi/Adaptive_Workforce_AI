# Production Configuration Audit — Phase 7

**Document Type:** Configuration Governance Record  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Configuration Locked — Requires Pre-Deployment Verification  
**Module:** `config/production_settings.py`

---

## 1. Purpose

Production configuration errors are a leading cause of data breaches and governance failures in enterprise software. A system that works correctly in development can expose employee data, bypass governance checks, or serve non-compliant outputs if a single environment variable is set incorrectly in production.

This document records the production configuration locks introduced in Phase 7, the rationale for each lock, the startup verification function that enforces them, and the items that require environment-specific configuration before deployment.

---

## 2. Configuration Lock Philosophy

Phase 7 separates configuration into two categories:

| Category | Mechanism | Overridable? |
|----------|-----------|-------------|
| **Governance locks** | Module-level Python constants in `production_settings.py` | No — requires code change + review |
| **Environment settings** | Environment variables via `.env` or secrets manager | Yes — deployment-specific |

Governance locks are constants, not environment variables. They cannot be overridden by setting `DEBUG=True` or `EMPLOYEE_LEVEL_OUTPUT_ENABLED=True` in an environment file. Overriding them requires a code change, which leaves a git diff that can be reviewed and audited.

---

## 3. Governance Lock Constants

The following constants are declared at module level in `config/production_settings.py`:

```python
DEBUG = False
SCIENTIFIC_FEATURE_MODE = "theory_grounded"
LEGACY_CONSTRUCTS_DISABLED = True
TEMPORAL_VALIDATION_ENABLED = True
LEAKAGE_DETECTION_ENABLED = True
CALIBRATION_REQUIRED = True
PDPL_WARNING_ENABLED = True
GOVERNANCE_DISCLAIMER_REQUIRED = True
EMPLOYEE_LEVEL_OUTPUT_ENABLED = False
AUDIT_LOGGING_ENABLED = True
CROSS_TENANT_ACCESS_ALLOWED = False
```

### 3.1 Rationale for Each Lock

| Lock | Rationale |
|------|-----------|
| `DEBUG = False` | Debug mode can expose stack traces, internal tenant IDs, and model internals to callers. Must never be True in production. |
| `SCIENTIFIC_FEATURE_MODE = "theory_grounded"` | Prevents regression to non-theory-grounded feature generation. COR Theory, JD-R Model, and FFM constructs must remain active. |
| `LEGACY_CONSTRUCTS_DISABLED = True` | Legacy columns (PDS, attendance_score) introduced leakage and non-calibrated proxies. Phase 5 identified and removed them; this lock prevents reintroduction. |
| `TEMPORAL_VALIDATION_ENABLED = True` | Temporal validation prevents training on future-leaked labels. Disabling it would silently produce inflated AUC scores. |
| `LEAKAGE_DETECTION_ENABLED = True` | Leakage detection prevents columns that directly encode the target from entering the feature set. Disabling creates a governance violation risk. |
| `CALIBRATION_REQUIRED = True` | Uncalibrated probabilities cannot be reliably communicated as risk indicators. CIPD and SHRM guidance requires calibration for HR analytics. |
| `PDPL_WARNING_ENABLED = True` | Saudi PDPL (Royal Decree M/19) requires data subjects to be informed of automated processing. The warning is the platform's technical control for this requirement. |
| `GOVERNANCE_DISCLAIMER_REQUIRED = True` | Every output must carry the disclaimer that this is probabilistic, not deterministic. Required for defensible HR use. |
| `EMPLOYEE_LEVEL_OUTPUT_ENABLED = False` | Individual employee risk scores in exported outputs violate PDPL data minimization principles and create unfair treatment risk under Saudi Labour Law. |
| `AUDIT_LOGGING_ENABLED = True` | Audit logging is required for regulatory traceability. Cannot be disabled. |
| `CROSS_TENANT_ACCESS_ALLOWED = False` | Multi-tenant isolation is a fundamental security property. Must never be True. |

---

## 4. `assert_production_governance_locks()`

The function `assert_production_governance_locks()` verifies all 11 locks at startup. Call it from the FastAPI `lifespan` event handler:

```python
# In backend/api/main.py
from contextlib import asynccontextmanager
from config.production_settings import assert_production_governance_locks

@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_production_governance_locks()   # Raises RuntimeError on failure
    yield

app = FastAPI(lifespan=lifespan)
```

If any lock fails verification, `RuntimeError` is raised with a descriptive message identifying the violated lock. The application will not start. This is intentional — a partially-configured system that has weakened governance locks is more dangerous than a system that refuses to start.

---

## 5. Allowed File Extensions

```python
ALLOWED_FILE_EXTENSIONS = frozenset({".csv", ".xlsx", ".xls", ".parquet"})
```

Explicitly excluded:
- `.pkl` — Python pickle files can execute arbitrary code on deserialization
- `.json` — JSON objects may carry nested employee PII without schema validation
- `.feather` — Less common format; no validation tooling configured

Only tabular formats with explicit schema validation are accepted.

---

## 6. Environment-Specific Settings

These settings are **not** governance locks — they vary by deployment environment and are read from environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `API_PORT` | `8000` | API server port |
| `API_HOST` | `0.0.0.0` | API bind address |
| `ARTIFACT_STORE_PATH` | `./data/artifacts` | Local artifact storage root |
| `AUDIT_LOG_PATH` | `./data/audit_logs` | Local audit log directory |
| `MODEL_STORE_PATH` | `./saved_models` | Trained model storage |
| `SAUDI_COMPLIANCE_MODE` | `true` | Activates Saudi-specific governance layers |

Production deployment must set `ENVIRONMENT=production`. The startup verification checks this and adjusts logging behavior.

---

## 7. Secrets Management Requirements

The following are NOT in `.env.example` or any committed file. They must be provided through a secrets manager in production:

| Secret | Required For | Recommended Source |
|--------|-------------|-------------------|
| `JWT_SECRET_KEY` | API authentication | AWS Secrets Manager / Azure Key Vault |
| `POSTGRES_PASSWORD` | Audit log persistence | Secrets manager or Kubernetes Secret |
| `REDIS_URL` | Job queue | Secrets manager |

The `.env.example` file documents which variables exist. The actual `.env` file must never be committed to version control (confirmed in `.gitignore`).

---

## 8. `get_settings_summary()`

Returns an audit-safe dictionary of the key production settings:

```python
{
    "debug": False,
    "scientific_feature_mode": "theory_grounded",
    "legacy_constructs_disabled": True,
    "temporal_validation_enabled": True,
    "leakage_detection_enabled": True,
    "calibration_required": True,
    "pdpl_warning_enabled": True,
    "governance_disclaimer_required": True,
    "employee_level_output_enabled": False,
    "audit_logging_enabled": True,
    "cross_tenant_access_allowed": False,
    "allowed_file_extensions": [".csv", ".xlsx", ".xls", ".parquet"],
}
```

This summary is safe to log at startup and include in compliance reports. It contains no secrets, no tenant data, and no model outputs.

---

## 9. Configuration Change Control

Any change to a governance lock constant must:

1. Be made in a separate branch (not directly to main)
2. Include a written justification in the PR description
3. Be reviewed by both the platform architect and a governance reviewer
4. Pass the full test suite (all 442+ tests)
5. Be recorded in this document with a rationale update

Removing or weakening a lock without following this process is a governance violation.

---

## 10. Test Verification Summary

Tests in `tests/test_phase7_tenant_isolation.py::TestProductionSettings`:

| Test | Verifies |
|------|---------|
| `test_debug_is_false` | DEBUG == False |
| `test_scientific_mode_is_theory_grounded` | SCIENTIFIC_FEATURE_MODE correct |
| `test_legacy_constructs_disabled` | LEGACY_CONSTRUCTS_DISABLED == True |
| `test_temporal_validation_enabled` | TEMPORAL_VALIDATION_ENABLED == True |
| `test_leakage_detection_enabled` | LEAKAGE_DETECTION_ENABLED == True |
| `test_calibration_required` | CALIBRATION_REQUIRED == True |
| `test_pdpl_warning_enabled` | PDPL_WARNING_ENABLED == True |
| `test_employee_level_output_disabled` | EMPLOYEE_LEVEL_OUTPUT_ENABLED == False |
| `test_audit_logging_enabled` | AUDIT_LOGGING_ENABLED == True |
| `test_cross_tenant_access_not_allowed` | CROSS_TENANT_ACCESS_ALLOWED == False |
| `test_allowed_file_extensions` | Frozenset matches expected extensions |
| `test_governance_lock_assertion_passes` | assert_production_governance_locks() completes |
| `test_settings_summary_has_no_secrets` | Summary dict contains no secret values |

All 13 tests pass as of 2026-05-20.

---

*Configuration locks are the lowest-cost, highest-reliability governance control. They cannot be misconfigured because they are code. This document must be updated whenever a lock is changed, and that change must go through formal review.*
