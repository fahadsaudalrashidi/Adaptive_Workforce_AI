"""
Phase 29 Extended — Test Suite.

Covers:
  - Risk Matrix component (file existence, exports)
  - Governance integrity for new modules

Phase 40: the Executive Readiness Engine (5-dimension compute/serialise),
API readiness wiring, TypeScript ReadinessAssessment types, CEO Dashboard
visualisation wiring, and Reports-page slide export button all tested
content that was deleted along with employee_risk_scoring.py and its
dependent pages/routes — see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.
RiskMatrix.tsx itself is unrelated to that removed system (a generic,
data-driven display component) and survives with its full test coverage.

Run with:  pytest tests/test_phase29_extended.py -v
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# =============================================================================
# Risk Matrix Component
# =============================================================================

class TestRiskMatrixComponent:
    def test_file_exists(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        assert path.exists(), "RiskMatrix.tsx should exist"

    def test_exports_risk_matrix(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        content = path.read_text(encoding="utf-8")
        assert "export function RiskMatrix" in content

    def test_has_likelihood_and_impact_axes(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        content = path.read_text(encoding="utf-8")
        assert "likelihood" in content.lower() or "LIKELIHOOD" in content
        assert "impact" in content.lower() or "IMPACT" in content

    def test_has_colour_coding(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        content = path.read_text(encoding="utf-8")
        # Should have green/amber/red colour coding
        assert "green" in content.lower() or "#15803d" in content or "emerald" in content.lower()
        assert "red" in content.lower() or "#991b1b" in content

    def test_has_governance_disclaimer(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        content = path.read_text(encoding="utf-8")
        assert "statistical" in content.lower() or "governance" in content.lower() or "HR review" in content

    def test_accepts_departments_prop(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        content = path.read_text(encoding="utf-8")
        assert "departments" in content


# =============================================================================
# Governance Integrity
# =============================================================================

class TestPhase29ExtendedGovernance:

    def test_risk_matrix_is_display_only(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "RiskMatrix.tsx"
        content = path.read_text(encoding="utf-8")
        assert "model.fit" not in content
        assert "sklearn" not in content
