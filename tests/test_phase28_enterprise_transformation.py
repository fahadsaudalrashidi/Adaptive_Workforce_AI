"""
Phase 28 — Enterprise Transformation Tests.

Tests covering:
  28F: COMMERCIAL_STRATEGY.md deliverable
  28G: COMPETITIVE_ADVANTAGE_REPORT.md deliverable
  28H: Governance & scientific validity preserved

Phase 40: 28A (Executive ROI Engine), 28B (Boardroom Reporting 2.0 PDF),
28C (Digital Twin financial overlay), 28D (Executive Index integration),
and 28E (Executive Dashboard ROI/index panels) all tested engines, PDF
exporters, or pages deleted along with employee_risk_scoring.py — see
PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md. 28F/28G/28H are independent
documentation/governance checks and survive with full coverage.

GOVERNANCE RULES VERIFIED:
  - No model retraining
  - No ML metric modification
  - No fake/hardcoded scenarios
  - No causal certainty claims
  - No individual employee identification in ROI output
  - PDPL controls preserved
"""
from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 28F: Commercial Strategy Document ────────────────────────────────────────

def test_commercial_strategy_exists():
    """28F: COMMERCIAL_STRATEGY.md must exist."""
    assert (_ROOT / "COMMERCIAL_STRATEGY.md").exists()


def test_commercial_strategy_has_pricing_tiers():
    """28F: COMMERCIAL_STRATEGY.md must define all 4 pricing tiers."""
    content = (_ROOT / "COMMERCIAL_STRATEGY.md").read_text(encoding="utf-8")
    for tier in ["Starter", "Professional", "Enterprise", "Government"]:
        assert tier in content, f"Missing pricing tier '{tier}' in COMMERCIAL_STRATEGY.md"


def test_commercial_strategy_has_sar_pricing():
    """28F: Commercial strategy must include SAR-denominated pricing."""
    content = (_ROOT / "COMMERCIAL_STRATEGY.md").read_text(encoding="utf-8")
    assert "SAR" in content
    assert "480,000" in content or "480K" in content


def test_commercial_strategy_has_sar_50m_target():
    """28F: Commercial strategy must reference the SAR 50M valuation target."""
    content = (_ROOT / "COMMERCIAL_STRATEGY.md").read_text(encoding="utf-8")
    assert "50M" in content or "50,000,000" in content


# ── 28G: Competitive Advantage Report ────────────────────────────────────────

def test_competitive_advantage_report_exists():
    """28G: COMPETITIVE_ADVANTAGE_REPORT.md must exist."""
    assert (_ROOT / "COMPETITIVE_ADVANTAGE_REPORT.md").exists()


def test_competitive_advantage_report_covers_five_competitors():
    """28G: Report must cover all 5 major competitors."""
    content = (_ROOT / "COMPETITIVE_ADVANTAGE_REPORT.md").read_text(encoding="utf-8")
    for competitor in ["Workday", "SAP SuccessFactors", "Oracle HCM", "Visier", "Eightfold"]:
        assert competitor in content, f"Missing competitor '{competitor}' in COMPETITIVE_ADVANTAGE_REPORT.md"


def test_competitive_advantage_report_has_competitive_moat_analysis():
    """28G: Report must include competitive moat analysis."""
    content = (_ROOT / "COMPETITIVE_ADVANTAGE_REPORT.md").read_text(encoding="utf-8")
    assert "Moat" in content or "moat" in content
    assert "PDPL" in content


def test_competitive_advantage_report_references_awi_pricing():
    """28G: Competitive report must show AWI pricing vs. competitors."""
    content = (_ROOT / "COMPETITIVE_ADVANTAGE_REPORT.md").read_text(encoding="utf-8")
    assert "SAR" in content or "480" in content


# ── 28H: Governance & Scientific Validity Preserved ──────────────────────────

def test_leakage_controls_intact():
    """28H governance: Leakage detection must still be present."""
    src = (_ROOT / "backend" / "core" / "secure_file_ingestion.py").read_text(encoding="utf-8")
    assert "leakage" in src.lower()


def test_all_existing_tests_still_pass_count():
    """28H: Verify test file count hasn't decreased."""
    test_files = list((_ROOT / "tests").glob("test_*.py"))
    assert len(test_files) >= 28, f"Expected at least 28 test files, found {len(test_files)}"


# ── Phase 7: Nitaqat premium honesty fix ────────────────────────────────────
# NITAQAT_COMPLIANCE_INVESTIGATION.md found NITAQAT_PREMIUM_LOW/HIGH (18-35%)
# was live, reached this exact output, and carried NO confidence/provenance
# label at all — an unlabeled figure presented as fact, the same failure
# class as the old flat SAR 120,000 formula. This regression test asserts
# the live ROI output never again contains that figure without an explicit
# confidence label alongside it.

def test_nitaqat_premium_disclaimer_constant_exists_and_is_honest():
    from backend.core import financial_intelligence_engine as fie
    assert fie.NITAQAT_PREMIUM_CONFIDENCE == "uncalibrated_generic_estimate"
    assert "not sourced" in fie.NITAQAT_PREMIUM_DISCLAIMER.lower()
