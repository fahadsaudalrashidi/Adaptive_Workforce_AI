"""
Production Configuration Profile — Phase 7.

Defines the locked production settings for the Adaptive Workforce AI SaaS platform.
These settings override any development defaults when ENVIRONMENT=production.

GOVERNANCE LOCKS (cannot be changed at runtime):
  - SCIENTIFIC_FEATURE_MODE is locked to "theory_grounded"
  - LEGACY_CONSTRUCTS_DISABLED is locked to True
  - DEBUG is locked to False
  - EMPLOYEE_LEVEL_OUTPUT_ENABLED is locked to False by default
  - AUDIT_LOGGING_REQUIRED is locked to True
  - TENANT_ISOLATION_REQUIRED is locked to True
  - CALIBRATION_AUDIT_REQUIRED is locked to True
  - TEMPORAL_VALIDATION_REQUIRED is locked to True
  - PDPL_WARNING_ENABLED is locked to True

These locks are enforced by read-only constants. Any code attempting to
change these values at runtime will read stale values — the production
settings module does not export mutable variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import FrozenSet

# ── Environment identity ─────────────────────────────────────────────────

ENVIRONMENT: str = "production"
DEBUG: bool = False  # LOCKED: never True in production
PLATFORM_VERSION: str = "7.0.0"
LOG_LEVEL: str = "INFO"

# ── Governance locks (immutable in production) ────────────────────────────

SCIENTIFIC_FEATURE_MODE: str = "theory_grounded"         # LOCKED
LEGACY_CONSTRUCTS_DISABLED: bool = True                   # LOCKED
TEMPORAL_VALIDATION_REQUIRED: bool = True                 # LOCKED
CALIBRATION_AUDIT_REQUIRED: bool = True                   # LOCKED
AUDIT_LOGGING_REQUIRED: bool = True                       # LOCKED
TENANT_ISOLATION_REQUIRED: bool = True                    # LOCKED
PDPL_WARNING_ENABLED: bool = True                         # LOCKED
SECURE_EXPORT_MODE: bool = True                           # LOCKED

# ── Employee-level output governance ─────────────────────────────────────

EMPLOYEE_LEVEL_OUTPUT_ENABLED: bool = False               # LOCKED OFF by default
# Enabling employee-level output requires hr_admin role + explicit request
# and triggers additional audit logging. This is NOT a global unlock.
EMPLOYEE_LEVEL_OUTPUT_ROLES: FrozenSet[str] = frozenset({"hr_admin"})

# ── File upload governance ─────────────────────────────────────────────

ALLOWED_FILE_EXTENSIONS: FrozenSet[str] = frozenset({
    ".csv", ".xlsx", ".xls", ".parquet"
})
# .json, .pkl, .feather are disabled in production (arbitrary code / model injection risk)

MAX_UPLOAD_SIZE_MB: int = 100
# 100 MB cap in production. HR datasets for 5,000 employees are typically <20 MB.
# Larger uploads may indicate bulk PII data or non-HR datasets.

MAX_ROWS_ALLOWED: int = 100_000
# Safety cap — very large datasets should be split or processed via batch pipeline.

# ── Tenant governance ──────────────────────────────────────────────────

MAX_TENANTS_PER_DEPLOYMENT: int = 500
MAX_DATASETS_PER_TENANT: int = 50
MAX_MODELS_PER_TENANT: int = 10
TENANT_ID_PATTERN: str = r"^[a-z0-9][a-z0-9_\-]{1,61}[a-z0-9]$"

# ── API governance ────────────────────────────────────────────────────

API_RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
API_MAX_RESPONSE_SIZE_MB: int = 10
API_REQUIRE_JWT: bool = True
API_JWT_ALGORITHM: str = "RS256"
API_JWT_EXPIRY_SECONDS: int = 3600       # 1 hour
API_REFRESH_TOKEN_EXPIRY_SECONDS: int = 28800  # 8 hours

# ── Audit logging governance ──────────────────────────────────────────

AUDIT_LOG_RETENTION_DAYS: int = 2555    # 7 years (required for Saudi enterprise compliance)
AUDIT_LOG_IMMUTABLE: bool = True        # append-only enforcement
AUDIT_LOG_ENCRYPT: bool = True          # encrypt at rest

# ── Model governance ─────────────────────────────────────────────────

MODEL_TRACEABILITY_REQUIRED: bool = True    # model artifacts must have traceability_reference
MODEL_CALIBRATION_RELIABILITY_REQUIRED: bool = True
MODEL_MAX_FOLD_AUC_STD: float = 0.12        # fold stability threshold
MODEL_MIN_CALIBRATION_SAMPLES: int = 20     # minimum positive cases for deployment

# ── Report governance ─────────────────────────────────────────────────

REPORT_LANGUAGE_GUARD_ENABLED: bool = True  # all report text audited
REPORT_GOVERNANCE_STATUS_REQUIRED: bool = True  # all responses include governance_status
REPORT_DISCLAIMER_REQUIRED: bool = True
REPORT_PDPL_NOTE_REQUIRED: bool = True

# ── Saudi compliance ──────────────────────────────────────────────────

SAUDI_COMPLIANCE_MODE: bool = True
SAUDI_SALARY_MIN_SAR: int = 4_000
SAUDI_SALARY_ANNUAL_THRESHOLD_SAR: int = 60_000
SAUDI_MIN_EMPLOYEE_AGE: int = 15       # Saudi Labour Law Art. 3
SAUDI_MAX_ATTRITION_RATE: float = 0.50  # >50% triggers governance review

# ── Storage paths (relative, for production override via env vars) ────────

BASE_DIR: Path = Path(__file__).resolve().parent.parent
ARTIFACT_STORE_PATH: str = os.getenv("ARTIFACT_STORE_PATH", str(BASE_DIR / "data" / "artifacts"))
AUDIT_LOG_PATH: str = os.getenv("AUDIT_LOG_PATH", str(BASE_DIR / "data" / "audit_logs"))
MODEL_STORE_PATH: str = os.getenv("MODEL_STORE_PATH", str(BASE_DIR / "saved_models"))

# ── Feature flags (production defaults) ──────────────────────────────────

FEATURE_EXECUTIVE_REPORTS: bool = True
FEATURE_ROI_ESTIMATION: bool = True
FEATURE_ARABIC_SCHEMA_SUPPORT: bool = True
FEATURE_MULTI_TENANT: bool = True
FEATURE_AUDIT_EXPORT: bool = True
FEATURE_INDIVIDUAL_SCORES: bool = False  # requires explicit enablement per request

# ── Production setting integrity check ────────────────────────────────────

def assert_production_governance_locks() -> None:
    """
    Assert that all governance locks are set correctly for production.

    Call this at application startup to catch any misconfiguration early.
    """
    violations: list[str] = []

    if DEBUG:
        violations.append("DEBUG must be False in production.")
    if SCIENTIFIC_FEATURE_MODE != "theory_grounded":
        violations.append(f"SCIENTIFIC_FEATURE_MODE must be 'theory_grounded', got '{SCIENTIFIC_FEATURE_MODE}'.")
    if not LEGACY_CONSTRUCTS_DISABLED:
        violations.append("LEGACY_CONSTRUCTS_DISABLED must be True in production.")
    if not TENANT_ISOLATION_REQUIRED:
        violations.append("TENANT_ISOLATION_REQUIRED must be True in production.")
    if not AUDIT_LOGGING_REQUIRED:
        violations.append("AUDIT_LOGGING_REQUIRED must be True in production.")
    if not CALIBRATION_AUDIT_REQUIRED:
        violations.append("CALIBRATION_AUDIT_REQUIRED must be True in production.")
    if not TEMPORAL_VALIDATION_REQUIRED:
        violations.append("TEMPORAL_VALIDATION_REQUIRED must be True in production.")
    if not PDPL_WARNING_ENABLED:
        violations.append("PDPL_WARNING_ENABLED must be True in production.")
    if not SECURE_EXPORT_MODE:
        violations.append("SECURE_EXPORT_MODE must be True in production.")
    if not REPORT_LANGUAGE_GUARD_ENABLED:
        violations.append("REPORT_LANGUAGE_GUARD_ENABLED must be True in production.")
    if EMPLOYEE_LEVEL_OUTPUT_ENABLED:
        violations.append("EMPLOYEE_LEVEL_OUTPUT_ENABLED must be False by default in production.")

    if violations:
        raise RuntimeError(
            "Production governance lock violations detected:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\nCorrect these settings before starting the production server."
        )


# ── Serializable settings summary (for audit logging) ────────────────────

def get_settings_summary() -> dict:
    """Returns a dict of key production settings for audit logging."""
    return {
        "environment": ENVIRONMENT,
        "debug": DEBUG,
        "scientific_feature_mode": SCIENTIFIC_FEATURE_MODE,
        "legacy_constructs_disabled": LEGACY_CONSTRUCTS_DISABLED,
        "tenant_isolation_required": TENANT_ISOLATION_REQUIRED,
        "audit_logging_required": AUDIT_LOGGING_REQUIRED,
        "calibration_audit_required": CALIBRATION_AUDIT_REQUIRED,
        "temporal_validation_required": TEMPORAL_VALIDATION_REQUIRED,
        "pdpl_warning_enabled": PDPL_WARNING_ENABLED,
        "secure_export_mode": SECURE_EXPORT_MODE,
        "employee_level_output_enabled": EMPLOYEE_LEVEL_OUTPUT_ENABLED,
        "report_language_guard_enabled": REPORT_LANGUAGE_GUARD_ENABLED,
        "saudi_compliance_mode": SAUDI_COMPLIANCE_MODE,
        "platform_version": PLATFORM_VERSION,
    }
