"""
Enterprise Audit Logger — Phase 7.

Provides structured, append-only audit logging for all governance-significant
events in the SaaS platform.

GOVERNANCE CONSTRAINT: No raw employee data is ever stored in audit log entries.
Log entries record events and their governance impact — not the underlying HR data
that triggered them. This is enforced by the AuditLogEntry dataclass having no
fields that can hold a DataFrame, employee record, or individual risk score.

In production, the log_event() method would write to an immutable, append-only
store (e.g., an audit log database with write-only IAM policy, or an append-only
cloud storage bucket). The in-memory store used here is a development approximation.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.core.tenant_isolation import validate_tenant_id, TenantValidationError

# ── Event type constants ────────────────────────────────────────────────────

EVT_TENANT_CREATED              = "tenant_created"
EVT_DATASET_UPLOADED            = "dataset_uploaded"
EVT_SCHEMA_SCAN_COMPLETED       = "schema_scan_completed"
EVT_GOVERNANCE_SCAN_COMPLETED   = "governance_scan_completed"
EVT_CONSTRUCT_ACTIVATED         = "construct_activated"
EVT_CONSTRUCT_BLOCKED           = "construct_blocked"
EVT_LEAKAGE_DETECTED            = "leakage_detected"
EVT_MODEL_TRAINING_STARTED      = "model_training_started"
EVT_MODEL_TRAINING_COMPLETED    = "model_training_completed"
EVT_REPORT_GENERATED            = "report_generated"
EVT_EXPORT_REQUESTED            = "export_requested"
EVT_COMPLIANCE_WARNING          = "compliance_warning_triggered"
EVT_ONBOARDING_COMPLETED        = "onboarding_completed"
EVT_ONBOARDING_BLOCKED          = "onboarding_blocked"
EVT_PII_DETECTED                = "pii_detected"
EVT_ACCESS_DENIED               = "access_denied"
EVT_CALIBRATION_COMPLETED       = "calibration_completed"
EVT_CALIBRATION_CRITICAL        = "calibration_critical"

_VALID_EVENT_TYPES = frozenset({
    EVT_TENANT_CREATED, EVT_DATASET_UPLOADED, EVT_SCHEMA_SCAN_COMPLETED,
    EVT_GOVERNANCE_SCAN_COMPLETED, EVT_CONSTRUCT_ACTIVATED, EVT_CONSTRUCT_BLOCKED,
    EVT_LEAKAGE_DETECTED, EVT_MODEL_TRAINING_STARTED, EVT_MODEL_TRAINING_COMPLETED,
    EVT_REPORT_GENERATED, EVT_EXPORT_REQUESTED, EVT_COMPLIANCE_WARNING,
    EVT_ONBOARDING_COMPLETED, EVT_ONBOARDING_BLOCKED, EVT_PII_DETECTED,
    EVT_ACCESS_DENIED, EVT_CALIBRATION_COMPLETED, EVT_CALIBRATION_CRITICAL,
})

# ── Severity constants ─────────────────────────────────────────────────────

SEV_INFO     = "INFO"
SEV_WARN     = "WARN"
SEV_HIGH     = "HIGH"
SEV_CRITICAL = "CRITICAL"

# ── Governance status constants ────────────────────────────────────────────

GOV_OK             = "OK"
GOV_WARNING        = "WARNING"
GOV_BLOCKED        = "BLOCKED"
GOV_UNDER_REVIEW   = "UNDER_REVIEW"

# ── Role constants ─────────────────────────────────────────────────────────

ROLE_SYSTEM      = "system"
ROLE_HR_ADMIN    = "hr_admin"
ROLE_HR_ANALYST  = "hr_analyst"
ROLE_EXECUTIVE   = "executive"
ROLE_DATA_SCI    = "data_scientist"
ROLE_AUDITOR     = "auditor"
ROLE_SYS_ADMIN   = "system_admin"


@dataclass(frozen=True)
class AuditLogEntry:
    """
    Immutable audit log record.

    GOVERNANCE: This dataclass intentionally has NO field that can contain
    raw employee data, individual risk scores, salary values, or personal
    identifiers. Summary must describe the event governance impact only.
    """
    event_id: str
    timestamp: str              # ISO 8601 UTC
    tenant_id: str
    actor_role: str
    event_type: str
    severity: str               # INFO / WARN / HIGH / CRITICAL
    governance_status: str      # OK / WARNING / BLOCKED / UNDER_REVIEW
    object_reference: str       # artifact_id, dataset_id, report_id, etc.
    summary: str                # human-readable event description (no employee data)
    metadata: dict = field(default_factory=dict)  # structured metadata (no PII)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "actor_role": self.actor_role,
            "event_type": self.event_type,
            "severity": self.severity,
            "governance_status": self.governance_status,
            "object_reference": self.object_reference,
            "summary": self.summary,
            "metadata": self.metadata,
        }


class AuditLogViolation(ValueError):
    """Raised when an attempt is made to log prohibited content."""


class AuditLogger:
    """
    Append-only audit logger for governance-significant events.

    In production, replace _store with a write-to-database or write-to-cloud
    implementation. The interface is identical — only the storage backend changes.

    Multi-tenant: entries are always tagged with tenant_id. The get_entries()
    method enforces that a tenant can only retrieve their own log entries.
    """

    def __init__(self) -> None:
        # In-memory store for development. Production: replace with DB/cloud backend.
        self._store: list[AuditLogEntry] = []

    def log_event(
        self,
        event_type: str,
        tenant_id: str,
        actor_role: str,
        severity: str,
        governance_status: str,
        object_reference: str,
        summary: str,
        metadata: Optional[dict] = None,
    ) -> AuditLogEntry:
        """
        Record a governance-significant event.

        Parameters
        ----------
        event_type : str
            One of the EVT_* constants.
        tenant_id : str
            Validated tenant identifier.
        actor_role : str
            Role of the user/system triggering the event.
        severity : str
            INFO / WARN / HIGH / CRITICAL.
        governance_status : str
            OK / WARNING / BLOCKED / UNDER_REVIEW.
        object_reference : str
            ID of the artifact, dataset, or report this event relates to.
        summary : str
            Human-readable description of the event. MUST NOT contain raw
            employee data, personal identifiers, or individual risk scores.
        metadata : dict, optional
            Structured metadata. MUST NOT contain raw employee data.
        """
        # Validate inputs
        try:
            validate_tenant_id(tenant_id)
        except TenantValidationError as e:
            raise AuditLogViolation(f"Cannot log event for invalid tenant_id: {e}") from e

        if event_type not in _VALID_EVENT_TYPES:
            raise AuditLogViolation(
                f"Unknown event_type '{event_type}'. "
                f"Use one of the EVT_* constants from audit_logger module."
            )

        # PII guard — reject summaries containing obvious PII patterns
        self._assert_no_pii_in_summary(summary)

        meta = dict(metadata or {})
        # Strip any DataFrame or complex objects that could contain employee data
        clean_meta = {
            k: v for k, v in meta.items()
            if isinstance(v, (str, int, float, bool, list, type(None)))
            and k not in ("df", "dataframe", "raw_data", "employee_data", "y_prob", "y_true")
        }

        entry = AuditLogEntry(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            tenant_id=tenant_id,
            actor_role=actor_role,
            event_type=event_type,
            severity=severity,
            governance_status=governance_status,
            object_reference=object_reference,
            summary=summary,
            metadata=clean_meta,
        )

        self._store.append(entry)
        return entry

    def get_entries(
        self,
        tenant_id: str,
        requesting_tenant_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[AuditLogEntry]:
        """
        Retrieve audit log entries for a tenant.

        If requesting_tenant_id is provided, enforces that it matches tenant_id
        (cross-tenant log access is denied).
        """
        if requesting_tenant_id is not None and requesting_tenant_id != tenant_id:
            self.log_event(
                event_type=EVT_ACCESS_DENIED,
                tenant_id=requesting_tenant_id,
                actor_role=ROLE_SYSTEM,
                severity=SEV_CRITICAL,
                governance_status=GOV_BLOCKED,
                object_reference=f"audit_log:{tenant_id}",
                summary=(
                    f"Cross-tenant audit log access attempt: "
                    f"tenant '{requesting_tenant_id}' attempted to read "
                    f"logs belonging to tenant '{tenant_id}'. Denied."
                ),
            )
            raise PermissionError(
                f"Tenant '{requesting_tenant_id}' cannot access audit logs "
                f"belonging to tenant '{tenant_id}'."
            )

        entries = [e for e in self._store if e.tenant_id == tenant_id]

        if event_type:
            entries = [e for e in entries if e.event_type == event_type]
        if severity:
            entries = [e for e in entries if e.severity == severity]

        return entries

    def get_all_critical_entries(self, tenant_id: str) -> list[AuditLogEntry]:
        """Retrieve all CRITICAL severity entries for a tenant (for compliance review)."""
        return self.get_entries(tenant_id, severity=SEV_CRITICAL)

    def entry_count(self, tenant_id: str) -> int:
        """Return total entry count for a tenant."""
        return sum(1 for e in self._store if e.tenant_id == tenant_id)

    def _assert_no_pii_in_summary(self, summary: str) -> None:
        """
        Reject summaries that appear to contain PII or employee-level data.

        This is a lightweight heuristic guard — not a comprehensive PII scanner.
        The primary PII protection is that AuditLogEntry has no field for raw data.
        """
        _PII_INDICATORS = [
            "national id", "national_id", "iqama", "رقم الهوية", "رقم_الهوية",
            "رقم الإقامة", "passport", "iban", r"sa\d{2}[a-z0-9]{18}",
            "employee record:", "raw data:", "monthly income:", "salary:",
        ]
        summary_lower = summary.lower()
        for indicator in _PII_INDICATORS:
            if indicator in summary_lower:
                raise AuditLogViolation(
                    f"Audit log summary appears to contain PII (matched: '{indicator}'). "
                    "Audit log summaries must describe governance events only — "
                    "never include employee identifiers, salary values, or personal data."
                )


# ── Module-level singleton (development/testing) ───────────────────────────
# In production, inject AuditLogger via dependency injection, not as a global.
_default_logger: Optional[AuditLogger] = None


def get_default_logger() -> AuditLogger:
    """Returns the module-level default logger instance (for development/testing)."""
    global _default_logger
    if _default_logger is None:
        _default_logger = AuditLogger()
    return _default_logger


def log_event(
    event_type: str,
    tenant_id: str,
    actor_role: str,
    severity: str,
    governance_status: str,
    object_reference: str,
    summary: str,
    metadata: Optional[dict] = None,
) -> AuditLogEntry:
    """Convenience function using the default logger."""
    return get_default_logger().log_event(
        event_type=event_type,
        tenant_id=tenant_id,
        actor_role=actor_role,
        severity=severity,
        governance_status=governance_status,
        object_reference=object_reference,
        summary=summary,
        metadata=metadata,
    )
