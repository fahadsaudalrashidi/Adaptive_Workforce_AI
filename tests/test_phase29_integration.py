"""
Phase 29 Integration Tests — Final Closure Round 2.

Covers:
  - Board Report V3 benchmark section
  - Board Report V3 storytelling section
  - BenchmarkGapPanel component wiring
  - Commercial Readiness panel in ExecutiveDashboard
  - Risk Matrix in ExecutiveDashboard
  - Storytelling panel in ExecutiveReports
  - Benchmark comparison in ExecutiveDashboard
  - PPTX exporter slide content verification
  - API endpoints functional test (benchmark compare/submit/sectors)
  - Governance integrity for all new sections

Run with:  pytest tests/test_phase29_integration.py -v
"""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI_SRC = ROOT / "executive-ui" / "src"


# ═══════════════════════════════════════════════════════════════════════════════
# Board Report V3 — Benchmark & Storytelling sections
# ═══════════════════════════════════════════════════════════════════════════════

# Phase 40: TestBoardReportV3Sections, TestExecutiveDashboardNewPanels,
# TestExecutiveReportsStorytelling, TestStoreTypes (fully) and 4 of
# TestIntegrationGovernance's 5 tests were removed — all exclusively
# referenced executive_pdf_exporter.py or ExecutiveDashboard.tsx/
# ExecutiveReports.tsx, all removed this phase. TestBenchmarkGapPanelComponent
# and TestBenchmarkAPIFunctional (independent, testing the real kept
# /benchmarks/* routes and BenchmarkGapPanel.tsx) are unaffected. See
# PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.


class TestBenchmarkGapPanelComponent:
    def _comp_src(self):
        return (UI_SRC / "components" / "visualizations" / "BenchmarkGapPanel.tsx").read_text(encoding="utf-8")

    def test_component_file_exists(self):
        assert (UI_SRC / "components" / "visualizations" / "BenchmarkGapPanel.tsx").exists()

    def test_exports_benchmark_gap_panel(self):
        assert "BenchmarkGapPanel" in self._comp_src()

    def test_has_sector_selector(self):
        src = self._comp_src()
        assert "SECTORS" in src or "sector" in src.lower()

    def test_has_gap_bars(self):
        src = self._comp_src()
        assert "org_value" in src
        assert "sector_mean" in src

    def test_dp_governance_note_present(self):
        src = self._comp_src()
        assert "differential privacy" in src.lower() or "k-anonymity" in src.lower() or "ε=0.5" in src

    def test_bilingual_support(self):
        src = self._comp_src()
        assert "isAr" in src or "label_ar" in src

    def test_on_request_comparison_prop(self):
        src = self._comp_src()
        assert "onRequestComparison" in src


# ═══════════════════════════════════════════════════════════════════════════════
# Executive Dashboard — new panels
# ═══════════════════════════════════════════════════════════════════════════════


class TestBenchmarkAPIFunctional:
    def _org_data(self):
        return {
            "executive_indices": {
                "indices": {
                    "wsi":  {"score": 65.0},
                    "rhi":  {"score": 70.0},
                    "tfri": {"score": 45.0},
                    "lsi":  {"score": 55.0},
                    "ori":  {"score": 60.0},
                    "hcri": {"score": 58.0},
                }
            },
            "total_employee_records": 800,
        }

    def test_sectors_endpoint_defined(self):
        src = (ROOT / "backend" / "api" / "local_analysis_routes.py").read_text()
        assert '/benchmarks/sectors' in src

    def test_compare_endpoint_defined(self):
        src = (ROOT / "backend" / "api" / "local_analysis_routes.py").read_text()
        assert '/benchmarks/compare' in src

    def test_submit_endpoint_defined(self):
        src = (ROOT / "backend" / "api" / "local_analysis_routes.py").read_text()
        assert '/benchmarks/submit' in src

    def test_compare_returns_gaps(self):
        from backend.core.benchmark_engine import get_benchmark_engine, benchmark_comparison_to_dict
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="banking",
                                employee_range="500-2000", period="Q2_2026")
        d = benchmark_comparison_to_dict(result)
        assert "gaps" in d
        assert isinstance(d["gaps"], list)

    def test_sectors_meet_k_anonymity(self):
        from backend.core.benchmark_engine import get_benchmark_engine, _K_MIN
        engine = get_benchmark_engine()
        sectors = engine.get_available_sectors()
        for s in sectors:
            assert s["n_contributors"] >= _K_MIN

    def test_benchmark_comparison_serialises_sector_label(self):
        from backend.core.benchmark_engine import get_benchmark_engine, benchmark_comparison_to_dict
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="banking",
                                employee_range="500-2000", period="Q2_2026")
        d = benchmark_comparison_to_dict(result)
        assert "sector" in d
        assert d["sector"] == "banking"

    def test_gap_has_significance_field(self):
        from backend.core.benchmark_engine import get_benchmark_engine, benchmark_comparison_to_dict
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="banking",
                                employee_range="500-2000", period="Q2_2026")
        d = benchmark_comparison_to_dict(result)
        valid = ("strength", "gap", "critical_gap", "neutral")
        for gap in d["gaps"]:
            assert "significance" in gap
            assert gap["significance"] in valid, \
                f"Unexpected significance value: {gap['significance']}"

    def test_submit_hashes_org(self):
        from backend.core.benchmark_engine import get_benchmark_engine
        engine = get_benchmark_engine()
        result = engine.submit_contribution(
            self._org_data(),
            sector="telecom",
            employee_range="500-2000",
            org_identifier="test_company_xyz",
        )
        assert "org_hash" in result
        assert result["org_hash"] != "test_company_xyz"


# ═══════════════════════════════════════════════════════════════════════════════
# Store types — BenchmarkComparison
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationGovernance:
    def test_benchmark_panel_no_individual_data(self):
        src = (UI_SRC / "components" / "visualizations" / "BenchmarkGapPanel.tsx").read_text()
        assert "individual employee" not in src.lower()

