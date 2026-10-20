"""
Tenant Isolation Model — Phase 7.

Provides the TenantContext and TenantIsolationGuard that enforce strict
namespace separation between tenants. All artifact paths, audit logs,
model storage, and report storage are namespaced under the tenant_id.

Design guarantee: tenant A cannot receive an artifact, report, or log
that belongs to tenant B. This is enforced structurally via namespace
prefixes and access validation, not via filtering logic that could be
bypassed.

Tenant IDs follow the pattern: [a-z0-9][a-z0-9_-]{1,61}[a-z0-9]
(lowercase alphanumeric, hyphens and underscores allowed in the middle)
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

# Tenant ID validation pattern (strict: 3–63 chars, slug-style)
_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_\-]{1,61}[a-z0-9]$")

# Artifact type constants (used for namespace prefixes)
ARTIFACT_DATASET = "dataset"
ARTIFACT_SCHEMA_REPORT = "schema_report"
ARTIFACT_GOVERNANCE_REPORT = "governance_report"
ARTIFACT_CONSTRUCT_REPORT = "construct_report"
ARTIFACT_CALIBRATION_REPORT = "calibration_report"
ARTIFACT_EXECUTIVE_REPORT = "executive_report"
ARTIFACT_AUDIT_PACKAGE = "audit_package"
ARTIFACT_MODEL = "model"
ARTIFACT_ONBOARDING_REPORT = "onboarding_report"
ARTIFACT_ROI_REPORT = "roi_report"

_VALID_ARTIFACT_TYPES = frozenset({
    ARTIFACT_DATASET,
    ARTIFACT_SCHEMA_REPORT,
    ARTIFACT_GOVERNANCE_REPORT,
    ARTIFACT_CONSTRUCT_REPORT,
    ARTIFACT_CALIBRATION_REPORT,
    ARTIFACT_EXECUTIVE_REPORT,
    ARTIFACT_AUDIT_PACKAGE,
    ARTIFACT_MODEL,
    ARTIFACT_ONBOARDING_REPORT,
    ARTIFACT_ROI_REPORT,
})


class TenantValidationError(ValueError):
    """Raised when tenant_id is invalid or access is denied."""


class CrossTenantAccessError(PermissionError):
    """Raised when a tenant attempts to access another tenant's resource."""


@dataclass(frozen=True)
class TenantContext:
    """
    Immutable context for a single tenant session.

    All namespace methods produce deterministic, tenant-scoped identifiers.
    No two tenants share a namespace prefix.
    """
    tenant_id: str

    def __post_init__(self) -> None:
        validate_tenant_id(self.tenant_id)

    # ── Namespace generators ────────────────────────────────────────────────

    def dataset_namespace(self, dataset_id: str) -> str:
        """Returns the tenant-scoped path for a dataset artifact."""
        return f"tenants/{self.tenant_id}/datasets/{dataset_id}"

    def artifact_namespace(self, artifact_type: str, artifact_id: str) -> str:
        """Returns the tenant-scoped path for any artifact."""
        if artifact_type not in _VALID_ARTIFACT_TYPES:
            raise TenantValidationError(
                f"Unknown artifact type '{artifact_type}'. "
                f"Valid types: {sorted(_VALID_ARTIFACT_TYPES)}"
            )
        return f"tenants/{self.tenant_id}/artifacts/{artifact_type}/{artifact_id}"

    def audit_namespace(self) -> str:
        """Returns the tenant-scoped audit log prefix."""
        return f"tenants/{self.tenant_id}/audit"

    def model_namespace(self, model_id: str) -> str:
        """Returns the tenant-scoped model storage path."""
        return f"tenants/{self.tenant_id}/models/{model_id}"

    def report_namespace(self, report_type: str, report_id: str) -> str:
        """Returns the tenant-scoped report path."""
        return f"tenants/{self.tenant_id}/reports/{report_type}/{report_id}"

    def temp_namespace(self, operation_id: str) -> str:
        """Returns the tenant-scoped temporary file path."""
        return f"tenants/{self.tenant_id}/tmp/{operation_id}"

    def owns(self, resource_path: str) -> bool:
        """Returns True if the resource_path is under this tenant's namespace."""
        return resource_path.startswith(f"tenants/{self.tenant_id}/")


class TenantIsolationGuard:
    """
    Validates cross-tenant access attempts.

    Stateless: every method call is independent.
    """

    def validate_access(
        self,
        requesting_tenant_id: str,
        resource_tenant_id: str,
    ) -> bool:
        """
        Returns True only if the requesting tenant owns the resource.

        Does NOT raise — use assert_access() for hard failures.
        """
        if not is_valid_tenant_id(requesting_tenant_id):
            return False
        if not is_valid_tenant_id(resource_tenant_id):
            return False
        return requesting_tenant_id == resource_tenant_id

    def assert_access(
        self,
        requesting_tenant_id: str,
        resource_tenant_id: str,
        resource_description: str = "resource",
    ) -> None:
        """
        Raises CrossTenantAccessError if tenant A attempts to access tenant B's resource.

        This is the hard gate: callers should use this to enforce isolation.
        """
        if not is_valid_tenant_id(requesting_tenant_id):
            raise TenantValidationError(
                f"Invalid requesting tenant_id: '{requesting_tenant_id}'"
            )
        if not is_valid_tenant_id(resource_tenant_id):
            raise TenantValidationError(
                f"Invalid resource tenant_id: '{resource_tenant_id}'"
            )
        if requesting_tenant_id != resource_tenant_id:
            raise CrossTenantAccessError(
                f"Tenant '{requesting_tenant_id}' attempted to access {resource_description} "
                f"belonging to tenant '{resource_tenant_id}'. Access denied."
            )

    def assert_path_ownership(
        self,
        requesting_tenant_id: str,
        resource_path: str,
    ) -> None:
        """
        Raises CrossTenantAccessError if the resource_path does not belong to the requesting tenant.
        """
        ctx = TenantContext(requesting_tenant_id)
        if not ctx.owns(resource_path):
            raise CrossTenantAccessError(
                f"Tenant '{requesting_tenant_id}' attempted to access path '{resource_path}' "
                "which is not under their namespace. Access denied."
            )


# ── Module-level convenience functions ─────────────────────────────────────

def validate_tenant_id(tenant_id: str) -> None:
    """Raises TenantValidationError if tenant_id does not conform to the allowed pattern."""
    if not tenant_id:
        raise TenantValidationError("tenant_id must not be empty.")
    if not isinstance(tenant_id, str):
        raise TenantValidationError(f"tenant_id must be a string, got {type(tenant_id).__name__}.")
    if not _TENANT_ID_PATTERN.match(tenant_id):
        raise TenantValidationError(
            f"Invalid tenant_id '{tenant_id}'. "
            "tenant_id must be 3–63 characters, lowercase alphanumeric, "
            "hyphens and underscores allowed in the middle (not at start/end)."
        )


def is_valid_tenant_id(tenant_id: str) -> bool:
    """Returns True if tenant_id is valid, False otherwise."""
    try:
        validate_tenant_id(tenant_id)
        return True
    except TenantValidationError:
        return False


def generate_tenant_scoped_id(tenant_id: str, prefix: str = "") -> str:
    """
    Generates a unique, tenant-scoped identifier.
    Format: {tenant_id}_{prefix}_{uuid4_hex[:12]}
    """
    validate_tenant_id(tenant_id)
    uid = uuid.uuid4().hex[:12]
    if prefix:
        return f"{tenant_id}_{prefix}_{uid}"
    return f"{tenant_id}_{uid}"


def make_tenant_context(tenant_id: str) -> TenantContext:
    """Convenience constructor with validation."""
    return TenantContext(tenant_id=tenant_id)
