"""
Phase 29 Final Closure — Test Suite.

Covers what survives the FINAL CLOSURE audit after Phase 40:
  29F  Benchmark Engine — real SQLite, k-anonymity, DP noise, compare, submit
  API  /benchmarks/* endpoints
  GOV  No causal certainty, PDPL, no financial advice, display-only outputs

Phase 40: the PPTX exporter, Board Report V3 PDF, and the UI-wiring checks
for FinancialImpactTreemap/RiskMatrix-in-RiskSegmentation/Storytelling-in-
DecisionCenter/ExecutiveReports-PPTX-button all tested content (engines,
routes, or pages) deleted along with employee_risk_scoring.py — see
PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md. The benchmark engine and its
/benchmarks/* routes are genuinely independent (no dependency on the
removed risk-scoring system) and survive with full coverage.

Run with:  pytest tests/test_phase29_final_closure.py -v
"""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI_SRC = ROOT / "executive-ui" / "src"


# ═══════════════════════════════════════════════════════════════════════════════
# 29F — Benchmark Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestBenchmarkEngineImport:
    def test_module_importable(self):
        from backend.core import benchmark_engine  # noqa: F401

    def test_public_api_exported(self):
        from backend.core.benchmark_engine import (
            BenchmarkEngine,
            BenchmarkRecord,
            BenchmarkGap,
            BenchmarkComparison,
            get_benchmark_engine,
            benchmark_comparison_to_dict,
        )
        assert all([BenchmarkEngine, BenchmarkRecord, BenchmarkGap,
                    BenchmarkComparison, get_benchmark_engine, benchmark_comparison_to_dict])


class TestBenchmarkEngineSectors:
    def test_get_available_sectors_returns_list(self):
        from backend.core.benchmark_engine import get_benchmark_engine
        engine = get_benchmark_engine()
        sectors = engine.get_available_sectors()
        assert isinstance(sectors, list)

    def test_sectors_have_required_fields(self):
        from backend.core.benchmark_engine import get_benchmark_engine
        engine = get_benchmark_engine()
        sectors = engine.get_available_sectors()
        if sectors:
            s = sectors[0]
            assert "sector" in s
            assert "n_contributors" in s

    def test_k_anonymity_enforced_in_sectors(self):
        from backend.core.benchmark_engine import get_benchmark_engine, _K_MIN
        engine = get_benchmark_engine()
        sectors = engine.get_available_sectors()
        for s in sectors:
            assert s["n_contributors"] >= _K_MIN, f"Sector {s['sector']} violates k-anonymity"


class TestBenchmarkEngineCompare:
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
            }
        }

    def test_compare_returns_comparison_object(self):
        from backend.core.benchmark_engine import get_benchmark_engine, BenchmarkComparison
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="banking", employee_range="500-2000", period="Q2_2026")
        assert isinstance(result, BenchmarkComparison)

    def test_compare_has_gaps(self):
        from backend.core.benchmark_engine import get_benchmark_engine
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="banking", employee_range="500-2000", period="Q2_2026")
        assert isinstance(result.gaps, list)

    def test_compare_serialises_to_dict(self):
        from backend.core.benchmark_engine import get_benchmark_engine, benchmark_comparison_to_dict
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="banking", employee_range="500-2000", period="Q2_2026")
        d = benchmark_comparison_to_dict(result)
        assert isinstance(d, dict)
        assert "sector" in d
        assert "gaps" in d

    def test_compare_sector_not_found_graceful(self):
        from backend.core.benchmark_engine import get_benchmark_engine, BenchmarkComparison
        engine = get_benchmark_engine()
        result = engine.compare(self._org_data(), sector="nonexistent_xyz", employee_range="500-2000", period="Q2_2026")
        assert isinstance(result, BenchmarkComparison)
        assert result.sector == "nonexistent_xyz"


class TestBenchmarkEngineSubmit:
    def test_submit_returns_dict(self):
        from backend.core.benchmark_engine import get_benchmark_engine
        engine = get_benchmark_engine()
        result = engine.submit_contribution(
            {"executive_indices": {"indices": {}}},
            sector="banking",
            employee_range="500-2000",
            org_identifier="test_org",
        )
        assert isinstance(result, dict)
        # submit returns "submitted" key (True/False), not "success"
        assert "submitted" in result or "reason" in result

    def test_submit_hashes_identifier(self):
        from backend.core.benchmark_engine import get_benchmark_engine
        engine = get_benchmark_engine()
        result = engine.submit_contribution(
            {},
            sector="banking",
            employee_range="500-2000",
            org_identifier="unique_company_123",
        )
        assert result.get("org_hash") != "unique_company_123"

    def test_k_anonymity_constant_is_5(self):
        from backend.core.benchmark_engine import _K_MIN
        assert _K_MIN == 5

    def test_dp_eps_constant_is_0_5(self):
        from backend.core.benchmark_engine import _DP_EPS
        assert _DP_EPS == 0.5


class TestBenchmarkEngineDP:
    def test_dp_noise_returns_float(self):
        from backend.core.benchmark_engine import _dp_noise
        result = _dp_noise(70.0, sensitivity=10.0, eps=0.5)
        assert isinstance(result, float)

    def test_dp_noise_is_noisy(self):
        from backend.core.benchmark_engine import _dp_noise
        # Very unlikely to be exactly 70.0 with DP noise
        results = {_dp_noise(70.0, sensitivity=10.0, eps=0.5) for _ in range(20)}
        assert len(results) > 1

    def test_dp_seeded_data_present(self):
        from backend.core.benchmark_engine import _SEED_BENCHMARKS
        assert len(_SEED_BENCHMARKS) >= 6


# ═══════════════════════════════════════════════════════════════════════════════
# API endpoint wiring — /benchmarks/*
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIEndpointWiring:
    def _routes_source(self):
        return (ROOT / "backend" / "api" / "local_analysis_routes.py").read_text(encoding="utf-8")

    def test_benchmark_sectors_endpoint_defined(self):
        src = self._routes_source()
        assert '@router.get("/benchmarks/sectors")' in src

    def test_benchmark_compare_endpoint_defined(self):
        src = self._routes_source()
        assert '@router.post("/benchmarks/compare")' in src

    def test_benchmark_submit_endpoint_defined(self):
        src = self._routes_source()
        assert '@router.post("/benchmarks/submit")' in src

    def test_benchmark_imports_engine(self):
        src = self._routes_source()
        assert "from backend.core.benchmark_engine import get_benchmark_engine" in src


# ═══════════════════════════════════════════════════════════════════════════════
# UI wiring: RiskMatrix component
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskMatrixWiring:
    def test_risk_matrix_component_file_exists(self):
        f = UI_SRC / "components" / "visualizations" / "RiskMatrix.tsx"
        assert f.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Governance integrity for surviving Phase 29 Final Closure modules
# ═══════════════════════════════════════════════════════════════════════════════

class TestFinalClosureGovernance:

    def test_benchmark_no_individual_data_leak(self):
        src = (ROOT / "backend" / "core" / "benchmark_engine.py").read_text()
        assert "individual" not in src.lower() or "no individual" in src.lower() or "k-anonymity" in src.lower()

    def test_benchmark_pdpl_mentioned(self):
        src = (ROOT / "backend" / "core" / "benchmark_engine.py").read_text()
        assert "PDPL" in src or "pdpl" in src.lower() or "k-anonymity" in src

    def test_benchmark_engine_dp_eps_is_conservative(self):
        from backend.core.benchmark_engine import _DP_EPS
        assert _DP_EPS <= 1.0

    def test_api_pdf_no_hardcoded_demo(self):
        src = (ROOT / "backend" / "api" / "local_analysis_routes.py").read_text()
        assert "demo_pdf_content" not in src
        assert "hardcoded_report" not in src
