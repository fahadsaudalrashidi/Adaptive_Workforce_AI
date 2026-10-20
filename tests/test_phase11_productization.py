"""
Phase 11 Productization Tests.

Covers:
  - LocalEnterpriseRuntime: start, tenant context, audit logging, caching,
    status reporting, tenant_id validation, offline guard integration
  - DemoDatasetManager: all 3 demo modes, isolation, DEMO_MODE tagging,
    available companies, mode switching

Phase 40: ExecutivePDFExporter (backend/core/executive_pdf_exporter.py) was
removed along with the ExecutiveReports.tsx page it exclusively served — its
8 tests here and the _sample_data() fixture they used were removed with it.
See PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import pandas as pd

from backend.core.local_enterprise_runtime import (
    LocalEnterpriseRuntime,
    get_runtime,
)
from backend.core.demo_dataset_manager import (
    DemoDatasetManager,
    DemoMode,
    DemoDatasetResult,
)


# ═══════════════════════════════════════════════════════════════════════════════
# LocalEnterpriseRuntime
# ═══════════════════════════════════════════════════════════════════════════════

class TestLocalEnterpriseRuntime:

    def setup_method(self):
        # Use a temp directory for each test
        self.tmp_dir = tempfile.mkdtemp()
        self.runtime = LocalEnterpriseRuntime(base_dir=Path(self.tmp_dir))

    def teardown_method(self):
        # Uninstall offline guard after each test to avoid contaminating global state
        from backend.core.offline_mode_guard import OfflineModeGuard
        g = OfflineModeGuard.get_instance()
        if g._installed:
            g.uninstall()
        # Reset runtime singleton for isolation
        LocalEnterpriseRuntime._instance = None

    # TEST 9 — Start installs offline guard and creates base directory
    def test_09_start_installs_offline_guard(self):
        from backend.core.offline_mode_guard import is_offline_guard_active
        self.runtime.start()
        assert is_offline_guard_active() is True
        assert Path(self.tmp_dir).exists()

    # TEST 10 — Tenant context creates correct directory structure
    def test_10_tenant_context_creates_directories(self):
        self.runtime.start()
        ctx = self.runtime.get_tenant_context("acme-corp")
        assert ctx.tenant_id == "acme-corp"
        assert ctx.directories_ready is True
        for sub in ["reports", "exports", "audit_logs", "cache", "uploads"]:
            assert (ctx.base_dir / sub).exists(), f"Missing subdir: {sub}"

    # TEST 11 — Audit log appends correctly and strips PII
    def test_11_audit_log_strips_pii(self):
        import json
        self.runtime.start()
        self.runtime.write_audit_event(
            "test-tenant",
            "model_inference",
            {
                "department": "IT",
                "national_id": "1029384756",   # PII — must be stripped
                "email": "user@example.com",    # PII — must be stripped
                "row_count": 500,
            },
        )
        ctx = self.runtime.get_tenant_context("test-tenant")
        log_path = ctx.audit_logs_dir / "audit.jsonl"
        assert log_path.exists()
        with open(log_path, encoding="utf-8") as f:
            event = json.loads(f.readline())
        assert event["payload"]["national_id"] == "[REDACTED]"
        assert event["payload"]["email"] == "[REDACTED]"
        assert event["payload"]["department"] == "IT"
        assert event["payload"]["row_count"] == 500

    # TEST 12 — Cache stores, retrieves, and respects tenant isolation
    def test_12_cache_tenant_isolation(self):
        self.runtime.start()
        self.runtime.cache_report("tenant-a", "report-1", "Content A")
        self.runtime.cache_report("tenant-b", "report-1", "Content B")
        assert self.runtime.get_cached_report("tenant-a", "report-1") == "Content A"
        assert self.runtime.get_cached_report("tenant-b", "report-1") == "Content B"
        # Clearing tenant-a cache should not affect tenant-b
        self.runtime.clear_tenant_cache("tenant-a")
        assert self.runtime.get_cached_report("tenant-a", "report-1") is None
        assert self.runtime.get_cached_report("tenant-b", "report-1") == "Content B"

    # TEST 13 — Status reports offline=False (platform is always offline)
    def test_13_runtime_status_is_always_offline(self):
        self.runtime.start()
        status = self.runtime.status()
        assert status.is_online is False
        assert status.offline_guard_active is True
        assert status.started_at != ""

    # TEST 14 — Malicious tenant_id (path traversal) is rejected
    def test_14_path_traversal_tenant_id_rejected(self):
        self.runtime.start()
        with pytest.raises(ValueError, match="path traversal"):
            self.runtime.get_tenant_context("../../../etc")
        with pytest.raises(ValueError, match="path traversal"):
            self.runtime.get_tenant_context("tenant/../../secret")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 15-20: DemoDatasetManager
# ═══════════════════════════════════════════════════════════════════════════════

class TestDemoDatasetManager:

    def setup_method(self):
        # Fresh instance per test
        DemoDatasetManager._instance = None
        self.mgr = DemoDatasetManager()

    # TEST 15 — Saudi attrition demo loads and is tagged DEMO_MODE
    def test_15_attrition_demo_tagged_demo_mode(self):
        result = self.mgr.load(DemoMode.SAUDI_ATTRITION, company_id="national-industrial-holdings")
        assert result.success is True
        assert result.demo_mode == DemoMode.SAUDI_ATTRITION
        assert result.attrition_modeling_allowed is True
        assert result.analysis_mode == "workforce_stability"
        assert result.readiness_level == "READY"
        assert result.dataset is not None
        assert result.dataset.attrs.get("DEMO_MODE") is True
        assert result.row_count > 0

    # TEST 16 — Jadarat market demo: attrition blocked, market intelligence
    def test_16_jadarat_market_demo_blocks_attrition(self):
        result = self.mgr.load(DemoMode.JADARAT_MARKET)
        assert result.success is True
        assert result.demo_mode == DemoMode.JADARAT_MARKET
        assert result.attrition_modeling_allowed is False
        assert result.analysis_mode == "market_intelligence"
        assert result.dataset is not None
        assert result.dataset.attrs.get("DEMO_MODE") is True
        assert result.row_count == 500  # fixed demo size

    # TEST 17 — Governance-blocked demo: BLOCKED readiness, explains PII/leakage
    def test_17_governance_blocked_demo_explains_controls(self):
        result = self.mgr.load(DemoMode.GOVERNANCE_BLOCKED)
        assert result.success is True
        assert result.readiness_level == "BLOCKED"
        assert result.attrition_modeling_allowed is False
        assert result.analysis_mode == "blocked"
        # PII and leakage must be flagged in governance_notes
        notes_combined = " ".join(result.governance_notes).lower()
        assert "pii" in notes_combined
        assert "leakage" in notes_combined

    # TEST 18 — Reset clears active mode, next load starts fresh
    def test_18_reset_clears_demo_state(self):
        self.mgr.load(DemoMode.SAUDI_ATTRITION, company_id="riyadh-healthcare-network")
        assert self.mgr.is_demo_active() is True
        self.mgr.reset()
        assert self.mgr.is_demo_active() is False
        assert self.mgr.get_active_mode() == DemoMode.NONE

    # TEST 19 — Available companies returns all 5 Saudi demo companies
    def test_19_available_companies_returns_five(self):
        companies = self.mgr.get_available_companies()
        assert len(companies) == 5
        ids = [c["company_id"] for c in companies]
        assert "national-industrial-holdings" in ids
        assert "saudi-digital-services" in ids
        assert "riyadh-healthcare-network" in ids

    # TEST 20 — Unknown company_id returns error result, not exception
    def test_20_unknown_company_returns_error_not_exception(self):
        result = self.mgr.load(DemoMode.SAUDI_ATTRITION, company_id="nonexistent-corp")
        assert result.success is False
        assert result.error is not None
        assert "nonexistent-corp" in result.error
        assert result.dataset is None
