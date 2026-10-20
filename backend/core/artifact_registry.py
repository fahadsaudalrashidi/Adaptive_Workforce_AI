"""
Artifact Registry — Phase 7.

Tracks all platform artifacts (datasets, reports, models, audit packages)
with tenant isolation, sensitivity classification, and governance metadata.

Governance invariants:
  - No artifact can be registered without a tenant_id
  - No artifact can be retrieved by a different tenant
  - Model artifacts require a traceability_reference (links to the
    OnboardingReport or theory audit that governs this model)
  - Sensitivity level is mandatory and drives access policy
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.core.tenant_isolation import (
    TenantContext,
    TenantIsolationGuard,
    CrossTenantAccessError,
    TenantValidationError,
    validate_tenant_id,
    ARTIFACT_MODEL,
    _VALID_ARTIFACT_TYPES,
)

# ── Sensitivity level constants ─────────────────────────────────────────────

SENSITIVITY_PUBLIC      = "PUBLIC"       # no personal data (executive aggregate reports)
SENSITIVITY_INTERNAL    = "INTERNAL"     # aggregated HR statistics (dept-level)
SENSITIVITY_CONFIDENTIAL = "CONFIDENTIAL"  # individual-level risk scores, governance reports
SENSITIVITY_RESTRICTED  = "RESTRICTED"   # model artifacts, audit packages, raw datasets

_VALID_SENSITIVITY_LEVELS = frozenset({
    SENSITIVITY_PUBLIC, SENSITIVITY_INTERNAL, SENSITIVITY_CONFIDENTIAL, SENSITIVITY_RESTRICTED,
})

# ── Default sensitivity by artifact type ───────────────────────────────────

_DEFAULT_SENSITIVITY: dict[str, str] = {
    "dataset":              SENSITIVITY_RESTRICTED,
    "schema_report":        SENSITIVITY_CONFIDENTIAL,
    "governance_report":    SENSITIVITY_CONFIDENTIAL,
    "construct_report":     SENSITIVITY_CONFIDENTIAL,
    "calibration_report":   SENSITIVITY_INTERNAL,
    "executive_report":     SENSITIVITY_INTERNAL,
    "audit_package":        SENSITIVITY_RESTRICTED,
    "model":                SENSITIVITY_RESTRICTED,
    "onboarding_report":    SENSITIVITY_CONFIDENTIAL,
    "roi_report":           SENSITIVITY_INTERNAL,
}

# ── Default retention policy by sensitivity ────────────────────────────────

_DEFAULT_RETENTION: dict[str, str] = {
    SENSITIVITY_PUBLIC:       "2_years",
    SENSITIVITY_INTERNAL:     "3_years",
    SENSITIVITY_CONFIDENTIAL: "5_years",
    SENSITIVITY_RESTRICTED:   "7_years",
}

# ── Access policy by sensitivity ──────────────────────────────────────────

_DEFAULT_ACCESS_POLICY: dict[str, str] = {
    SENSITIVITY_PUBLIC:       "hr_admin,hr_analyst,executive,auditor",
    SENSITIVITY_INTERNAL:     "hr_admin,hr_analyst,executive",
    SENSITIVITY_CONFIDENTIAL: "hr_admin,hr_analyst",
    SENSITIVITY_RESTRICTED:   "hr_admin",
}


class ArtifactRegistryError(ValueError):
    """Raised on registry validation failures."""


@dataclass(frozen=True)
class ArtifactRecord:
    """
    Immutable record for a registered platform artifact.

    Sensitivity level and access policy are set at registration time
    and cannot be changed without creating a new artifact version.
    """
    artifact_id: str
    tenant_id: str
    artifact_type: str
    created_at: str                         # ISO 8601 UTC
    checksum: str                           # SHA-256 of serialized content
    governance_status: str                  # OK / WARNING / BLOCKED / UNDER_REVIEW
    sensitivity_level: str                  # PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED
    retention_policy: str                   # "2_years", "7_years", etc.
    access_policy: str                      # comma-separated role list
    namespace_path: str                     # tenant-scoped storage path
    traceability_reference: Optional[str]   # required for MODEL artifacts
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "tenant_id": self.tenant_id,
            "artifact_type": self.artifact_type,
            "created_at": self.created_at,
            "checksum": self.checksum,
            "governance_status": self.governance_status,
            "sensitivity_level": self.sensitivity_level,
            "retention_policy": self.retention_policy,
            "access_policy": self.access_policy,
            "namespace_path": self.namespace_path,
            "traceability_reference": self.traceability_reference,
            "metadata": self.metadata,
        }


class ArtifactRegistry:
    """
    In-memory artifact registry for development.

    In production, replace self._store with a database table or object
    storage metadata index. The public interface is unchanged.

    All access is tenant-scoped. Attempting to retrieve an artifact
    with the wrong tenant_id raises CrossTenantAccessError.
    """

    def __init__(self) -> None:
        self._store: dict[str, ArtifactRecord] = {}
        self._guard = TenantIsolationGuard()

    def register(
        self,
        tenant_id: str,
        artifact_type: str,
        content: object,
        governance_status: str = "OK",
        sensitivity_level: Optional[str] = None,
        retention_policy: Optional[str] = None,
        access_policy: Optional[str] = None,
        traceability_reference: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ArtifactRecord:
        """
        Register a new artifact and return its record.

        Parameters
        ----------
        tenant_id : str
            Owning tenant. Required.
        artifact_type : str
            One of the ARTIFACT_* constants.
        content : object
            The artifact content (for checksum computation). Raw employee data
            must never be passed here — content should be a serializable report
            or metadata dict.
        governance_status : str
            Current governance status of this artifact.
        sensitivity_level : str, optional
            If not provided, defaults to the artifact_type's default sensitivity.
        traceability_reference : str, optional
            Required for MODEL artifacts — must reference the OnboardingReport
            or audit document that governs this model.
        """
        validate_tenant_id(tenant_id)

        if artifact_type not in _VALID_ARTIFACT_TYPES:
            raise ArtifactRegistryError(
                f"Unknown artifact_type '{artifact_type}'. "
                f"Valid types: {sorted(_VALID_ARTIFACT_TYPES)}"
            )

        # Model artifacts require a traceability reference
        if artifact_type == ARTIFACT_MODEL and not traceability_reference:
            raise ArtifactRegistryError(
                "Model artifacts require a traceability_reference. "
                "Provide the OnboardingReport ID or audit document reference "
                "that governs this model's training."
            )

        ctx = TenantContext(tenant_id)
        artifact_id = str(uuid.uuid4())
        namespace_path = ctx.artifact_namespace(artifact_type, artifact_id)

        # Compute checksum of serialized content
        checksum = self._compute_checksum(content)

        sens = sensitivity_level or _DEFAULT_SENSITIVITY.get(artifact_type, SENSITIVITY_CONFIDENTIAL)
        if sens not in _VALID_SENSITIVITY_LEVELS:
            raise ArtifactRegistryError(
                f"Invalid sensitivity_level '{sens}'. "
                f"Use one of: {sorted(_VALID_SENSITIVITY_LEVELS)}"
            )

        retention = retention_policy or _DEFAULT_RETENTION[sens]
        access = access_policy or _DEFAULT_ACCESS_POLICY[sens]

        record = ArtifactRecord(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            artifact_type=artifact_type,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            checksum=checksum,
            governance_status=governance_status,
            sensitivity_level=sens,
            retention_policy=retention,
            access_policy=access,
            namespace_path=namespace_path,
            traceability_reference=traceability_reference,
            metadata=dict(metadata or {}),
        )

        self._store[artifact_id] = record
        return record

    def get(
        self,
        artifact_id: str,
        requesting_tenant_id: str,
    ) -> ArtifactRecord:
        """
        Retrieve an artifact record.

        Raises CrossTenantAccessError if the requesting tenant does not own the artifact.
        Raises KeyError if artifact_id does not exist.
        """
        validate_tenant_id(requesting_tenant_id)

        if artifact_id not in self._store:
            raise KeyError(f"Artifact '{artifact_id}' not found in registry.")

        record = self._store[artifact_id]
        self._guard.assert_access(
            requesting_tenant_id=requesting_tenant_id,
            resource_tenant_id=record.tenant_id,
            resource_description=f"artifact '{artifact_id}' (type={record.artifact_type})",
        )
        return record

    def list_for_tenant(
        self,
        tenant_id: str,
        artifact_type: Optional[str] = None,
    ) -> list[ArtifactRecord]:
        """Return all artifacts owned by a tenant, optionally filtered by type."""
        validate_tenant_id(tenant_id)
        records = [r for r in self._store.values() if r.tenant_id == tenant_id]
        if artifact_type:
            records = [r for r in records if r.artifact_type == artifact_type]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records

    def exists(self, artifact_id: str, tenant_id: str) -> bool:
        """Returns True if the artifact exists and belongs to the given tenant."""
        try:
            self.get(artifact_id, tenant_id)
            return True
        except (KeyError, CrossTenantAccessError):
            return False

    def total_count(self, tenant_id: str) -> int:
        """Return total artifact count for a tenant."""
        validate_tenant_id(tenant_id)
        return sum(1 for r in self._store.values() if r.tenant_id == tenant_id)

    @staticmethod
    def _compute_checksum(content: object) -> str:
        """Compute a SHA-256 checksum of the content for integrity tracking."""
        try:
            if hasattr(content, "to_dict"):
                serialized = json.dumps(content.to_dict(), sort_keys=True, default=str)
            elif isinstance(content, dict):
                serialized = json.dumps(content, sort_keys=True, default=str)
            elif isinstance(content, str):
                serialized = content
            else:
                serialized = str(content)
        except Exception:
            serialized = repr(content)
        return hashlib.sha256(serialized.encode()).hexdigest()
