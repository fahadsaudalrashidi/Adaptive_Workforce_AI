"""
Phase 30 — AWI Enterprise Productization Tests

Covers:
- 30A: PRODUCT_IDENTITY.md created and valid
- 30C: tenant_manager.py — TenantManager + TenantProfile + TenantTier
- 30E: historical_intelligence_engine.py — WorkforceSnapshot + TrendAnalysis
- Document existence checks for 30D, 30F, 30G, 30H
"""
import json
import tempfile
from pathlib import Path

import pytest

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent


# ── 30A: PRODUCT_IDENTITY.md ──────────────────────────────────────────────────

class TestProductIdentity:
    """30A — PRODUCT_IDENTITY.md content validation."""

    def test_product_identity_exists(self):
        assert (ROOT / "PRODUCT_IDENTITY.md").exists()

    def test_product_identity_has_product_name(self):
        content = (ROOT / "PRODUCT_IDENTITY.md").read_text(encoding="utf-8")
        assert "AWI" in content
        assert "Adaptive Workforce Intelligence" in content

    def test_product_identity_has_differentiators(self):
        content = (ROOT / "PRODUCT_IDENTITY.md").read_text(encoding="utf-8")
        assert "Differentiator" in content

    def test_product_identity_has_value_propositions(self):
        content = (ROOT / "PRODUCT_IDENTITY.md").read_text(encoding="utf-8")
        assert "Executive Value Proposition" in content
        assert "Government Value Proposition" in content
        assert "Enterprise Value Proposition" in content

    def test_product_identity_has_platform_metrics(self):
        content = (ROOT / "PRODUCT_IDENTITY.md").read_text(encoding="utf-8")
        assert "0.8471" in content or "AUC" in content

    def test_product_identity_no_demo_references(self):
        content = (ROOT / "PRODUCT_IDENTITY.md").read_text(encoding="utf-8")
        assert "Demo Mode" not in content
        assert "Graduation Project" not in content
        assert "Academic Project" not in content


# ── 30C: TenantManager ─────────────────────────────────────────────────────────

class TestTenantManager:
    """30C — Multi-tenant foundation."""

    @pytest.fixture
    def manager(self, tmp_path):
        from backend.core.tenant_manager import TenantManager
        return TenantManager(db_path=str(tmp_path / "test_tenants.db"))

    def test_create_tenant(self, manager):
        from backend.core.tenant_manager import TenantTier
        profile = manager.create_tenant(
            org_name="Test Bank",
            tenant_id="test-bank-01",
            tier=TenantTier.PROFESSIONAL,
        )
        assert profile.tenant_id == "test-bank-01"
        assert profile.org_name == "Test Bank"
        assert profile.tier.value == "professional"

    def test_get_tenant(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Test Co", "test-co-01", tier=TenantTier.STARTER)
        profile = manager.get_tenant("test-co-01")
        assert profile is not None
        assert profile.org_name == "Test Co"

    def test_get_nonexistent_tenant_returns_none(self, manager):
        result = manager.get_tenant("does-not-exist-xx")
        assert result is None

    def test_list_tenants(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Alpha Corp", "alpha-corp-01", tier=TenantTier.ENTERPRISE)
        manager.create_tenant("Beta Corp", "beta-corp-01", tier=TenantTier.STARTER)
        tenants = manager.list_tenants()
        ids = [t.tenant_id for t in tenants]
        assert "alpha-corp-01" in ids
        assert "beta-corp-01" in ids

    def test_tier_limits(self, manager):
        from backend.core.tenant_manager import TenantTier
        profile = manager.create_tenant("Big Corp", "big-corp-01", tier=TenantTier.ENTERPRISE)
        assert profile.tier_limits["max_employees"] == 10000
        assert profile.tier_limits["api_access"] is True
        assert profile.tier_limits["sso"] is True

    def test_can_analyze_employees_within_limit(self, manager):
        from backend.core.tenant_manager import TenantTier
        profile = manager.create_tenant("Small Biz", "small-biz-01", tier=TenantTier.STARTER)
        assert profile.can_analyze_employees(400) is True

    def test_cannot_analyze_employees_over_limit(self, manager):
        from backend.core.tenant_manager import TenantTier
        profile = manager.create_tenant("Small Biz 2", "small-biz-02", tier=TenantTier.STARTER)
        assert profile.can_analyze_employees(600) is False

    def test_government_unlimited_employees(self, manager):
        from backend.core.tenant_manager import TenantTier
        profile = manager.create_tenant("Gov Min", "gov-min-01", tier=TenantTier.GOVERNMENT)
        assert profile.can_analyze_employees(100000) is True

    def test_create_session(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Session Test", "session-test-01", tier=TenantTier.PROFESSIONAL)
        session = manager.create_session("session-test-01")
        assert session.tenant_id == "session-test-01"
        assert session.session_id.startswith("session-test-01")
        assert session.analysis_count == 0

    def test_record_analysis(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Track Org", "track-org-01", tier=TenantTier.ENTERPRISE)
        session = manager.create_session("track-org-01")
        manager.record_analysis(session.session_id, "track-org-01")
        manager.record_analysis(session.session_id, "track-org-01")

    def test_record_export(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Export Org", "export-org-01", tier=TenantTier.ENTERPRISE)
        session = manager.create_session("export-org-01")
        manager.record_export(session.session_id, "export-org-01", "board_report_v3")

    def test_deactivate_tenant(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Old Corp", "old-corp-01", tier=TenantTier.STARTER)
        manager.deactivate_tenant("old-corp-01")
        profile = manager.get_tenant("old-corp-01")
        assert profile.is_active is False

    def test_deactivated_tenant_excluded_from_list(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Dead Corp", "dead-corp-01", tier=TenantTier.STARTER)
        manager.deactivate_tenant("dead-corp-01")
        active_ids = [t.tenant_id for t in manager.list_tenants(active_only=True)]
        assert "dead-corp-01" not in active_ids

    def test_audit_log(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Audit Co", "audit-co-01", tier=TenantTier.PROFESSIONAL)
        log = manager.get_audit_log("audit-co-01")
        assert len(log) >= 1
        assert log[0]["event_type"] == "tenant_created"

    def test_usage_summary(self, manager):
        from backend.core.tenant_manager import TenantTier
        manager.create_tenant("Usage Co", "usage-co-01", tier=TenantTier.ENTERPRISE)
        summary = manager.get_usage_summary("usage-co-01")
        assert summary["tenant_id"] == "usage-co-01"
        assert summary["tier"] == "enterprise"
        assert "tier_limits" in summary

    def test_provision_default_tenant(self, manager):
        from backend.core.tenant_manager import provision_default_tenant
        profile = provision_default_tenant(
            org_name="Default Org",
            tenant_id="awi-test-default",
            manager=manager,
        )
        assert profile.tenant_id == "awi-test-default"
        # idempotent
        profile2 = provision_default_tenant(
            org_name="Default Org",
            tenant_id="awi-test-default",
            manager=manager,
        )
        assert profile2.tenant_id == profile.tenant_id

    def test_tenant_to_dict(self, manager):
        from backend.core.tenant_manager import TenantTier
        profile = manager.create_tenant("Dict Test", "dict-test-01", tier=TenantTier.PROFESSIONAL)
        d = profile.to_dict()
        assert d["tenant_id"] == "dict-test-01"
        assert d["tier"] == "professional"
        assert "tier_limits" in d

    def test_invalid_tenant_id_raises(self, manager):
        from backend.core.tenant_isolation import TenantValidationError
        with pytest.raises(TenantValidationError):
            manager.create_tenant("Bad", tenant_id="INVALID TENANT ID!")


# Phase 40: TestHistoricalIntelligenceEngine (30E) removed along with
# backend/core/historical_intelligence_engine.py — see
# PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.



# ── 30D, 30F, 30G, 30H: Document existence ────────────────────────────────────

class TestPhase30Documents:
    """Validate all Phase 30 documents exist and have meaningful content."""

    DOCS = [
        "PRODUCT_IDENTITY.md",
        "MULTITENANT_FOUNDATION.md",
        "ENTERPRISE_AUTH_ROADMAP.md",
        "HISTORICAL_INTELLIGENCE_ENGINE.md",
        "BENCHMARK_EVOLUTION_REPORT.md",
        "AWI_PRODUCT_MATURITY_REPORT.md",
        "COMMERCIALIZATION_PACKAGE.md",
    ]

    @pytest.mark.parametrize("doc", DOCS)
    def test_document_exists(self, doc):
        assert (ROOT / doc).exists(), f"Missing: {doc}"

    @pytest.mark.parametrize("doc", DOCS)
    def test_document_not_empty(self, doc):
        content = (ROOT / doc).read_text(encoding="utf-8")
        assert len(content) > 500, f"Document too short: {doc}"

    def test_enterprise_auth_has_sso(self):
        content = (ROOT / "ENTERPRISE_AUTH_ROADMAP.md").read_text(encoding="utf-8")
        assert "Entra ID" in content or "SAML" in content

    def test_auth_has_rbac(self):
        content = (ROOT / "ENTERPRISE_AUTH_ROADMAP.md").read_text(encoding="utf-8")
        assert "RBAC" in content

    def test_multitenant_has_tiers(self):
        content = (ROOT / "MULTITENANT_FOUNDATION.md").read_text(encoding="utf-8")
        assert "Enterprise" in content
        assert "Government" in content

    def test_commercialization_has_pricing(self):
        content = (ROOT / "COMMERCIALIZATION_PACKAGE.md").read_text(encoding="utf-8")
        assert "SAR" in content
        assert "120,000" in content or "120000" in content

    def test_maturity_report_has_overall_score(self):
        content = (ROOT / "AWI_PRODUCT_MATURITY_REPORT.md").read_text(encoding="utf-8")
        assert "82.5" in content or "Overall" in content

    def test_benchmark_report_has_sectors(self):
        content = (ROOT / "BENCHMARK_EVOLUTION_REPORT.md").read_text(encoding="utf-8")
        assert "Banking" in content
        assert "Government" in content

    def test_historical_engine_has_pdpl_notes(self):
        content = (ROOT / "HISTORICAL_INTELLIGENCE_ENGINE.md").read_text(encoding="utf-8")
        assert "PDPL" in content

    def test_no_demo_in_documents(self):
        forbidden = ["Demo Mode", "Graduation Project", "Academic Project"]
        for doc in self.DOCS:
            content = (ROOT / doc).read_text(encoding="utf-8")
            for term in forbidden:
                assert term not in content, f"Found '{term}' in {doc}"


# ── 30D: Auth Role/Permission Taxonomy ─────────────────────────────────────────
# Phase 34.5: auth_session.py's dormant, credential-less session-management
# subsystem (AuthSessionManager, AWIUser/AWISession, ensure_local_admin_user,
# and its unused 3-table schema sharing data/awi_auth.db with the real,
# credentialed local_auth.py system) was removed as dead/unsafe scaffold
# code — see auth_session.py's module docstring and PHASE_4_MODULES_REPORT.md.
# Only the genuinely live role/permission taxonomy remains, and only it is
# tested here.

class TestAuthSessionFoundation:
    """30D — RBAC role enum and permission matrix (real, imported by local_auth.py)."""

    def test_roles_defined(self):
        from backend.core.auth_session import AWIRole
        assert AWIRole.CHRO.value == "chro"
        assert AWIRole.HR_ANALYST.value == "hr_analyst"
        assert AWIRole.AUDITOR.value == "auditor"
        assert AWIRole.SYSTEM_ADMIN.value == "system_admin"

    def test_permission_matrix_has_entries(self):
        from backend.core.auth_session import PERMISSION_MATRIX
        assert "run_analysis" in PERMISSION_MATRIX
        assert "manage_tenants" in PERMISSION_MATRIX
        assert "view_audit_log" in PERMISSION_MATRIX

    def test_chro_can_run_analysis(self):
        from backend.core.auth_session import PERMISSION_MATRIX, AWIRole
        assert AWIRole.CHRO in PERMISSION_MATRIX["run_analysis"]

    def test_auditor_cannot_run_analysis(self):
        from backend.core.auth_session import PERMISSION_MATRIX, AWIRole
        assert AWIRole.AUDITOR not in PERMISSION_MATRIX["run_analysis"]

    def test_system_admin_manages_tenants(self):
        from backend.core.auth_session import PERMISSION_MATRIX, AWIRole
        assert AWIRole.SYSTEM_ADMIN in PERMISSION_MATRIX["manage_tenants"]
        assert AWIRole.HR_ANALYST not in PERMISSION_MATRIX["manage_tenants"]

    def test_dormant_session_manager_no_longer_exists(self):
        """Regression guard: the removed subsystem must not silently reappear."""
        import backend.core.auth_session as mod
        for name in ("AuthSessionManager", "AWIUser", "AWISession",
                     "ensure_local_admin_user", "get_auth_manager"):
            assert not hasattr(mod, name), (
                f"auth_session.{name} reappeared — this was intentionally removed "
                "as dormant, credential-less scaffold code (Phase 34.5). If it is "
                "being reintroduced deliberately, it must be wired into the live "
                "auth flow and reviewed for the missing credential check, not "
                "left dormant again."
            )


# ── 30F: Benchmark Extensions ─────────────────────────────────────────────────

class TestBenchmarkExtensions:
    """30F — compare_internal_departments + get_historical_position."""

    @pytest.fixture
    def engine(self, tmp_path, monkeypatch):
        import backend.core.benchmark_engine as _bm
        monkeypatch.setattr(_bm, "_DB_PATH", tmp_path / "test_bm.sqlite")
        from backend.core.benchmark_engine import BenchmarkEngine
        return BenchmarkEngine()

    def _dept_summary(self, n_depts: int = 3) -> list[dict]:
        depts = []
        for i in range(n_depts):
            depts.append({
                "department": f"Dept_{i}",
                "employee_count": 100 + i * 50,
                "avg_risk_score": 40.0 + i * 5,
                "avg_stability_score": 70.0 - i * 5,
                "risk_band_counts": {
                    "Stable":           60 + i * 5,
                    "Monitoring":       25,
                    "Strategic Concern": 10,
                    "Priority Review":  5 - min(i, 4),
                },
            })
        return depts

    def test_compare_internal_departments_available(self, engine):
        result = engine.compare_internal_departments(self._dept_summary(3))
        assert result["available"] is True
        assert result["department_count"] == 3

    def test_compare_internal_departments_ranks_departments(self, engine):
        result = engine.compare_internal_departments(self._dept_summary(4))
        assert "rankings" in result
        assert len(result["rankings"]) == 4
        # top performing should have highest WSI
        top = result["rankings"][0]
        for r in result["rankings"][1:]:
            assert top["wsi_proxy"] >= r["wsi_proxy"]

    def test_compare_internal_departments_empty_returns_unavailable(self, engine):
        result = engine.compare_internal_departments([])
        assert result["available"] is False

    def test_compare_internal_departments_single_dept_unavailable(self, engine):
        result = engine.compare_internal_departments(self._dept_summary(1))
        assert result["available"] is False

    def test_compare_internal_departments_has_governance_note(self, engine):
        result = engine.compare_internal_departments(self._dept_summary(3))
        assert "governance_note" in result
        assert len(result["governance_note"]) > 20

    def test_get_historical_position_requires_snapshots(self, engine):
        result = engine.get_historical_position([], "banking")
        assert result["available"] is False

    def test_get_historical_position_with_improving_trend(self, engine, monkeypatch):
        snapshots = [
            {"executive_indices": {"wsi": 60.0}, "risk_band_counts": {}, "total_employee_records": 500, "period_label": "2025-Q1"},
            {"executive_indices": {"wsi": 64.0}, "risk_band_counts": {}, "total_employee_records": 500, "period_label": "2025-Q2"},
            {"executive_indices": {"wsi": 69.0}, "risk_band_counts": {}, "total_employee_records": 500, "period_label": "2025-Q3"},
        ]
        result = engine.get_historical_position(snapshots, "banking")
        assert result["available"] is True
        assert result["n_snapshots"] == 3
        assert result["trajectory"] == "improving"

    def test_get_historical_position_with_declining_trend(self, engine):
        snapshots = [
            {"executive_indices": {"wsi": 80.0}, "risk_band_counts": {}, "total_employee_records": 500, "period_label": "2025-Q1"},
            {"executive_indices": {"wsi": 73.0}, "risk_band_counts": {}, "total_employee_records": 500, "period_label": "2025-Q2"},
            {"executive_indices": {"wsi": 65.0}, "risk_band_counts": {}, "total_employee_records": 500, "period_label": "2025-Q3"},
        ]
        result = engine.get_historical_position(snapshots, "banking")
        assert result["available"] is True
        assert result["trajectory"] == "declining"

    def test_get_historical_position_no_wsi_returns_unavailable(self, engine):
        snapshots = [
            {"executive_indices": {}, "risk_band_counts": {}, "total_employee_records": 500},
        ]
        result = engine.get_historical_position(snapshots, "banking")
        assert result["available"] is False

    # Phase 40: test_routes_module_imports_with_phase30_engines removed —
    # _tenant_manager/_history_engine were removed from local_analysis_routes.py
    # along with the shared-upload/session pipeline that was their only real
    # caller. TestTenantManager above is unaffected (tenant_manager.py itself
    # was kept — it has no other tie to the removed prediction system).
    # TestHistoricalIntelligenceEngine (30E) was removed separately, above,
    # since historical_intelligence_engine.py itself was removed. See
    # PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.
