"""
Phase 7 — Tenant Isolation & Infrastructure Tests.

Covers:
  - TenantContext namespace generation
  - TenantIsolationGuard cross-tenant access blocking
  - AuditLogger tenant scoping and PII guard
  - ArtifactRegistry tenant isolation
  - Production settings governance locks
  - Enterprise API routes tenant scoping
  - governance_status presence in API responses
"""

from __future__ import annotations

import pytest

from backend.core.tenant_isolation import (
    TenantContext,
    TenantIsolationGuard,
    TenantValidationError,
    CrossTenantAccessError,
    validate_tenant_id,
    is_valid_tenant_id,
    generate_tenant_scoped_id,
    make_tenant_context,
    ARTIFACT_DATASET,
    ARTIFACT_MODEL,
    ARTIFACT_EXECUTIVE_REPORT,
)
from backend.core.audit_logger import (
    AuditLogger,
    AuditLogEntry,
    AuditLogViolation,
    EVT_TENANT_CREATED,
    EVT_DATASET_UPLOADED,
    EVT_LEAKAGE_DETECTED,
    EVT_ONBOARDING_COMPLETED,
    SEV_INFO,
    SEV_CRITICAL,
    GOV_OK,
    GOV_BLOCKED,
    ROLE_HR_ADMIN,
    ROLE_SYSTEM,
)
from backend.core.artifact_registry import (
    ArtifactRegistry,
    ArtifactRegistryError,
    SENSITIVITY_RESTRICTED,
    SENSITIVITY_PUBLIC,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TestTenantContext
# ═══════════════════════════════════════════════════════════════════════════════

class TestTenantContext:

    def test_valid_tenant_id_accepted(self):
        ctx = TenantContext(tenant_id="acme-corp")
        assert ctx.tenant_id == "acme-corp"

    def test_invalid_tenant_id_rejected_empty(self):
        with pytest.raises(TenantValidationError):
            TenantContext(tenant_id="")

    def test_invalid_tenant_id_rejected_uppercase(self):
        with pytest.raises(TenantValidationError):
            TenantContext(tenant_id="ACME")

    def test_invalid_tenant_id_rejected_starts_with_hyphen(self):
        with pytest.raises(TenantValidationError):
            TenantContext(tenant_id="-acme")

    def test_invalid_tenant_id_rejected_too_short(self):
        with pytest.raises(TenantValidationError):
            TenantContext(tenant_id="ab")

    def test_dataset_namespace_is_tenant_scoped(self):
        ctx = TenantContext("tenant-a")
        path = ctx.dataset_namespace("ds-001")
        assert path.startswith("tenants/tenant-a/")
        assert "ds-001" in path

    def test_artifact_namespace_is_tenant_scoped(self):
        ctx = TenantContext("tenant-a")
        path = ctx.artifact_namespace(ARTIFACT_EXECUTIVE_REPORT, "rpt-001")
        assert path.startswith("tenants/tenant-a/")
        assert "rpt-001" in path

    def test_model_namespace_is_tenant_scoped(self):
        ctx = TenantContext("tenant-a")
        path = ctx.model_namespace("model-v1")
        assert path.startswith("tenants/tenant-a/")

    def test_audit_namespace_is_tenant_scoped(self):
        ctx = TenantContext("tenant-a")
        path = ctx.audit_namespace()
        assert path.startswith("tenants/tenant-a/")

    def test_owns_correct_path(self):
        ctx = TenantContext("tenant-a")
        assert ctx.owns("tenants/tenant-a/datasets/ds-001")

    def test_does_not_own_other_tenant_path(self):
        ctx = TenantContext("tenant-a")
        assert not ctx.owns("tenants/tenant-b/datasets/ds-001")

    def test_different_tenants_have_different_namespaces(self):
        ctx_a = TenantContext("tenant-a")
        ctx_b = TenantContext("tenant-b")
        path_a = ctx_a.dataset_namespace("same-id")
        path_b = ctx_b.dataset_namespace("same-id")
        assert path_a != path_b

    def test_invalid_artifact_type_raises(self):
        ctx = TenantContext("tenant-a")
        with pytest.raises(TenantValidationError):
            ctx.artifact_namespace("invalid_type", "art-001")

    def test_is_valid_tenant_id_true(self):
        assert is_valid_tenant_id("acme-corp") is True

    def test_is_valid_tenant_id_false(self):
        assert is_valid_tenant_id("ACME") is False
        assert is_valid_tenant_id("") is False
        assert is_valid_tenant_id("ab") is False

    def test_generate_tenant_scoped_id_is_unique(self):
        ids = {generate_tenant_scoped_id("tenant-a", "dataset") for _ in range(20)}
        assert len(ids) == 20  # all unique


# ═══════════════════════════════════════════════════════════════════════════════
# TestTenantIsolationGuard
# ═══════════════════════════════════════════════════════════════════════════════

class TestTenantIsolationGuard:

    def setup_method(self):
        self.guard = TenantIsolationGuard()

    def test_same_tenant_access_allowed(self):
        assert self.guard.validate_access("tenant-a", "tenant-a") is True

    def test_cross_tenant_access_denied(self):
        assert self.guard.validate_access("tenant-a", "tenant-b") is False

    def test_assert_access_passes_for_same_tenant(self):
        self.guard.assert_access("tenant-a", "tenant-a")  # no exception

    def test_assert_access_raises_for_cross_tenant(self):
        with pytest.raises(CrossTenantAccessError):
            self.guard.assert_access("tenant-a", "tenant-b")

    def test_assert_access_error_message_contains_tenant_ids(self):
        with pytest.raises(CrossTenantAccessError) as exc_info:
            self.guard.assert_access("tenant-a", "tenant-b", "report 'rpt-001'")
        assert "tenant-a" in str(exc_info.value)
        assert "tenant-b" in str(exc_info.value)

    def test_assert_access_invalid_requesting_tenant_raises_validation_error(self):
        with pytest.raises(TenantValidationError):
            self.guard.assert_access("INVALID", "tenant-b")

    def test_assert_path_ownership_passes_for_own_path(self):
        self.guard.assert_path_ownership("tenant-a", "tenants/tenant-a/datasets/ds-001")

    def test_assert_path_ownership_raises_for_other_tenant_path(self):
        with pytest.raises(CrossTenantAccessError):
            self.guard.assert_path_ownership("tenant-a", "tenants/tenant-b/datasets/ds-001")


# ═══════════════════════════════════════════════════════════════════════════════
# TestAuditLogger
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogger:

    def setup_method(self):
        self.logger = AuditLogger()

    def test_log_event_returns_entry(self):
        entry = self.logger.log_event(
            event_type=EVT_TENANT_CREATED,
            tenant_id="tenant-a",
            actor_role=ROLE_HR_ADMIN,
            severity=SEV_INFO,
            governance_status=GOV_OK,
            object_reference="tenant:tenant-a",
            summary="Tenant created.",
        )
        assert isinstance(entry, AuditLogEntry)

    def test_entry_has_all_required_fields(self):
        entry = self.logger.log_event(
            event_type=EVT_DATASET_UPLOADED,
            tenant_id="tenant-a",
            actor_role=ROLE_HR_ADMIN,
            severity=SEV_INFO,
            governance_status=GOV_OK,
            object_reference="dataset:ds-001",
            summary="Dataset metadata registered.",
        )
        assert entry.event_id
        assert entry.timestamp
        assert entry.tenant_id == "tenant-a"
        assert entry.event_type == EVT_DATASET_UPLOADED
        assert entry.severity == SEV_INFO

    def test_audit_logger_never_stores_raw_employee_data(self):
        """AuditLogEntry has no field for DataFrames or individual employee records."""
        entry = self.logger.log_event(
            event_type=EVT_ONBOARDING_COMPLETED,
            tenant_id="tenant-a",
            actor_role=ROLE_HR_ADMIN,
            severity=SEV_INFO,
            governance_status=GOV_OK,
            object_reference="dataset:ds-001",
            summary="Onboarding completed. 200 rows processed.",
        )
        entry_dict = entry.to_dict()
        # No DataFrame fields
        assert "df" not in entry_dict
        assert "dataframe" not in entry_dict
        assert "raw_data" not in entry_dict
        assert "employee_data" not in entry_dict

    def test_pii_in_summary_is_rejected(self):
        with pytest.raises(AuditLogViolation):
            self.logger.log_event(
                event_type=EVT_LEAKAGE_DETECTED,
                tenant_id="tenant-a",
                actor_role=ROLE_SYSTEM,
                severity=SEV_CRITICAL,
                governance_status=GOV_BLOCKED,
                object_reference="dataset:ds-001",
                summary="Employee national id: 1234567890 was found in column.",
            )

    def test_get_entries_returns_only_own_tenant_entries(self):
        self.logger.log_event(
            event_type=EVT_TENANT_CREATED, tenant_id="tenant-a",
            actor_role=ROLE_SYSTEM, severity=SEV_INFO, governance_status=GOV_OK,
            object_reference="tenant:tenant-a", summary="Tenant A created.",
        )
        self.logger.log_event(
            event_type=EVT_TENANT_CREATED, tenant_id="tenant-b",
            actor_role=ROLE_SYSTEM, severity=SEV_INFO, governance_status=GOV_OK,
            object_reference="tenant:tenant-b", summary="Tenant B created.",
        )
        entries_a = self.logger.get_entries("tenant-a")
        assert all(e.tenant_id == "tenant-a" for e in entries_a)

    def test_cross_tenant_log_access_raises(self):
        self.logger.log_event(
            event_type=EVT_TENANT_CREATED, tenant_id="tenant-b",
            actor_role=ROLE_SYSTEM, severity=SEV_INFO, governance_status=GOV_OK,
            object_reference="tenant:tenant-b", summary="Tenant B created.",
        )
        with pytest.raises(PermissionError):
            self.logger.get_entries("tenant-b", requesting_tenant_id="tenant-a")

    def test_invalid_event_type_rejected(self):
        with pytest.raises(AuditLogViolation):
            self.logger.log_event(
                event_type="made_up_event",
                tenant_id="tenant-a",
                actor_role=ROLE_HR_ADMIN,
                severity=SEV_INFO,
                governance_status=GOV_OK,
                object_reference="test",
                summary="This should fail.",
            )

    def test_invalid_tenant_id_rejected(self):
        with pytest.raises(AuditLogViolation):
            self.logger.log_event(
                event_type=EVT_TENANT_CREATED,
                tenant_id="INVALID_UPPERCASE",
                actor_role=ROLE_HR_ADMIN,
                severity=SEV_INFO,
                governance_status=GOV_OK,
                object_reference="test",
                summary="This should fail.",
            )

    def test_metadata_strips_dataframe_keys(self):
        import pandas as pd
        entry = self.logger.log_event(
            event_type=EVT_DATASET_UPLOADED,
            tenant_id="tenant-a",
            actor_role=ROLE_HR_ADMIN,
            severity=SEV_INFO,
            governance_status=GOV_OK,
            object_reference="dataset:ds-001",
            summary="Dataset uploaded.",
            metadata={"df": pd.DataFrame({"a": [1, 2]}), "row_count": 200},
        )
        assert "df" not in entry.metadata
        assert entry.metadata.get("row_count") == 200


# ═══════════════════════════════════════════════════════════════════════════════
# TestArtifactRegistry
# ═══════════════════════════════════════════════════════════════════════════════

class TestArtifactRegistry:

    def setup_method(self):
        self.registry = ArtifactRegistry()

    def test_register_artifact_returns_record(self):
        record = self.registry.register(
            tenant_id="tenant-a",
            artifact_type=ARTIFACT_DATASET,
            content={"row_count": 200},
        )
        assert record.artifact_id
        assert record.tenant_id == "tenant-a"
        assert record.artifact_type == ARTIFACT_DATASET

    def test_artifact_requires_tenant_id(self):
        with pytest.raises(TenantValidationError):
            self.registry.register(
                tenant_id="",
                artifact_type=ARTIFACT_DATASET,
                content={},
            )

    def test_model_artifact_requires_traceability_reference(self):
        with pytest.raises(ArtifactRegistryError):
            self.registry.register(
                tenant_id="tenant-a",
                artifact_type=ARTIFACT_MODEL,
                content={"model": "weights"},
                traceability_reference=None,
            )

    def test_model_artifact_with_traceability_succeeds(self):
        record = self.registry.register(
            tenant_id="tenant-a",
            artifact_type=ARTIFACT_MODEL,
            content={"model": "weights"},
            traceability_reference="onboarding_report:or-001",
        )
        assert record.traceability_reference == "onboarding_report:or-001"

    def test_get_artifact_returns_own_tenant_record(self):
        record = self.registry.register(
            tenant_id="tenant-a",
            artifact_type=ARTIFACT_DATASET,
            content={"row_count": 100},
        )
        retrieved = self.registry.get(record.artifact_id, requesting_tenant_id="tenant-a")
        assert retrieved.artifact_id == record.artifact_id

    def test_cross_tenant_artifact_access_blocked(self):
        record = self.registry.register(
            tenant_id="tenant-a",
            artifact_type=ARTIFACT_DATASET,
            content={"row_count": 100},
        )
        with pytest.raises(CrossTenantAccessError):
            self.registry.get(record.artifact_id, requesting_tenant_id="tenant-b")

    def test_namespace_path_is_tenant_scoped(self):
        record = self.registry.register(
            tenant_id="tenant-a",
            artifact_type=ARTIFACT_DATASET,
            content={},
        )
        assert record.namespace_path.startswith("tenants/tenant-a/")

    def test_sensitivity_level_defaults_by_type(self):
        dataset_record = self.registry.register(
            tenant_id="tenant-a",
            artifact_type=ARTIFACT_DATASET,
            content={},
        )
        assert dataset_record.sensitivity_level == SENSITIVITY_RESTRICTED

    def test_checksum_is_deterministic(self):
        content = {"key": "value", "count": 42}
        r1 = self.registry.register("tenant-a", ARTIFACT_DATASET, content)
        r2 = self.registry.register("tenant-a", ARTIFACT_DATASET, content)
        assert r1.checksum == r2.checksum

    def test_list_for_tenant_returns_only_own_artifacts(self):
        self.registry.register("tenant-a", ARTIFACT_DATASET, {"n": 1})
        self.registry.register("tenant-b", ARTIFACT_DATASET, {"n": 2})
        records = self.registry.list_for_tenant("tenant-a")
        assert all(r.tenant_id == "tenant-a" for r in records)

    def test_artifact_not_found_raises_key_error(self):
        with pytest.raises(KeyError):
            self.registry.get("nonexistent-id", requesting_tenant_id="tenant-a")

    def test_total_count_per_tenant(self):
        self.registry.register("tenant-a", ARTIFACT_DATASET, {})
        self.registry.register("tenant-a", ARTIFACT_DATASET, {})
        self.registry.register("tenant-b", ARTIFACT_DATASET, {})
        assert self.registry.total_count("tenant-a") == 2
        assert self.registry.total_count("tenant-b") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TestProductionSettings
# ═══════════════════════════════════════════════════════════════════════════════

class TestProductionSettings:

    def test_debug_is_false(self):
        from config.production_settings import DEBUG
        assert DEBUG is False

    def test_scientific_feature_mode_is_theory_grounded(self):
        from config.production_settings import SCIENTIFIC_FEATURE_MODE
        assert SCIENTIFIC_FEATURE_MODE == "theory_grounded"

    def test_legacy_constructs_disabled(self):
        from config.production_settings import LEGACY_CONSTRUCTS_DISABLED
        assert LEGACY_CONSTRUCTS_DISABLED is True

    def test_tenant_isolation_required(self):
        from config.production_settings import TENANT_ISOLATION_REQUIRED
        assert TENANT_ISOLATION_REQUIRED is True

    def test_audit_logging_required(self):
        from config.production_settings import AUDIT_LOGGING_REQUIRED
        assert AUDIT_LOGGING_REQUIRED is True

    def test_pdpl_warning_enabled(self):
        from config.production_settings import PDPL_WARNING_ENABLED
        assert PDPL_WARNING_ENABLED is True

    def test_employee_level_output_disabled_by_default(self):
        from config.production_settings import EMPLOYEE_LEVEL_OUTPUT_ENABLED
        assert EMPLOYEE_LEVEL_OUTPUT_ENABLED is False

    def test_secure_export_mode_enabled(self):
        from config.production_settings import SECURE_EXPORT_MODE
        assert SECURE_EXPORT_MODE is True

    def test_calibration_audit_required(self):
        from config.production_settings import CALIBRATION_AUDIT_REQUIRED
        assert CALIBRATION_AUDIT_REQUIRED is True

    def test_temporal_validation_required(self):
        from config.production_settings import TEMPORAL_VALIDATION_REQUIRED
        assert TEMPORAL_VALIDATION_REQUIRED is True

    def test_governance_lock_assertion_passes(self):
        from config.production_settings import assert_production_governance_locks
        assert_production_governance_locks()  # must not raise

    def test_settings_summary_contains_key_fields(self):
        from config.production_settings import get_settings_summary
        summary = get_settings_summary()
        assert summary["debug"] is False
        assert summary["scientific_feature_mode"] == "theory_grounded"
        assert summary["legacy_constructs_disabled"] is True
        assert summary["pdpl_warning_enabled"] is True
        assert summary["employee_level_output_enabled"] is False

    def test_allowed_file_extensions(self):
        from config.production_settings import ALLOWED_FILE_EXTENSIONS
        assert ".csv" in ALLOWED_FILE_EXTENSIONS
        assert ".xlsx" in ALLOWED_FILE_EXTENSIONS
        # Dangerous types excluded
        assert ".pkl" not in ALLOWED_FILE_EXTENSIONS
        assert ".exe" not in ALLOWED_FILE_EXTENSIONS


# ═══════════════════════════════════════════════════════════════════════════════
# TestEnterpriseAPIRoutes
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnterpriseAPIRoutes:

    def test_enterprise_routes_module_importable(self):
        from backend.api.enterprise_routes import router
        assert router is not None

    def test_governance_status_model_importable(self):
        from backend.api.enterprise_routes import GovernanceStatus
        gs = GovernanceStatus(status="OK")
        assert gs.status == "OK"
        assert gs.disclaimer  # non-empty

    def test_tenant_create_response_model_importable(self):
        from backend.api.enterprise_routes import TenantCreateResponse, GovernanceStatus
        import datetime
        resp = TenantCreateResponse(
            tenant_id="test-corp",
            display_name="Test Corp",
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            governance_status=GovernanceStatus(status="OK"),
            onboarding_checklist=["Step 1", "Step 2"],
        )
        assert resp.tenant_id == "test-corp"
        assert len(resp.onboarding_checklist) >= 1

    def test_onboarding_response_includes_governance_status(self):
        from backend.api.enterprise_routes import OnboardingResponse, GovernanceStatus
        resp = OnboardingResponse(
            job_id="job-001",
            tenant_id="tenant-a",
            overall_status="READY",
            deployment_readiness_score=0.9,
            erp_system_detected="IBM_HR_BENCHMARK",
            erp_confidence="HIGH",
            theory_compatible_constructs=["SatisfactionIndex"],
            blocked_constructs=[],
            blocking_issues=[],
            governance_warnings=[],
            governance_status=GovernanceStatus(status="OK"),
            summary="All good.",
        )
        assert resp.governance_status.status == "OK"

    def test_executive_report_response_has_no_individual_data_field(self):
        from backend.api.enterprise_routes import ExecutiveReportResponse
        import inspect
        fields = set(ExecutiveReportResponse.model_fields.keys())
        # No individual-level fields
        assert "y_prob" not in fields
        assert "individual_risk_score" not in fields
        assert "employee_id" not in fields
        assert "employee_number" not in fields
