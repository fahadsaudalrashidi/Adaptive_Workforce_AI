"""
Phase 29 — Executive Experience Domination Test Suite.

Tests all Phase 29 sub-phases:
  29G — Premium Visualisation Components (file presence, key exports)
  29F — Benchmark Engine Roadmap (document completeness)
  29I — UX Navigation Groups (sidebar grouping)

Phase 40: 29B (CEO Dashboard), 29C (Board Report V3), 29D (Storytelling
Engine), 29E (API storytelling wiring), 29H (Slide export) all tested
content that was deleted along with employee_risk_scoring.py and its
dependent pages/routes — see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.
The one 29B test with real remaining value (Sidebar grouping) is folded
into 29I above; TestCEODashboardWiring itself checked NavPage for 'ceo',
which no longer exists.

Run with:  pytest tests/test_phase29_executive_experience.py -v
"""

from __future__ import annotations
import os
import sys
import json
from pathlib import Path

# ── Root path setup ───────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# =============================================================================
# 29F — Benchmark Engine Roadmap
# =============================================================================

class TestBenchmarkRoadmap:
    def test_file_exists(self):
        path = ROOT / "BENCHMARK_ENGINE_ROADMAP.md"
        assert path.exists(), "BENCHMARK_ENGINE_ROADMAP.md not found"

    def test_has_privacy_section(self):
        path = ROOT / "BENCHMARK_ENGINE_ROADMAP.md"
        content = path.read_text(encoding="utf-8")
        assert "k-anonymity" in content.lower() or "k-anonymit" in content.lower() or "k_anonymity" in content.lower()

    def test_has_differential_privacy(self):
        path = ROOT / "BENCHMARK_ENGINE_ROADMAP.md"
        content = path.read_text(encoding="utf-8")
        assert "differential privacy" in content.lower()

    def test_has_pdpl_section(self):
        path = ROOT / "BENCHMARK_ENGINE_ROADMAP.md"
        content = path.read_text(encoding="utf-8")
        assert "pdpl" in content.lower()

    def test_has_phases(self):
        path = ROOT / "BENCHMARK_ENGINE_ROADMAP.md"
        content = path.read_text(encoding="utf-8")
        assert "Phase 31" in content

    def test_has_sql_schema(self):
        path = ROOT / "BENCHMARK_ENGINE_ROADMAP.md"
        content = path.read_text(encoding="utf-8")
        assert "CREATE TABLE" in content


# =============================================================================
# 29G — Visualisation Components
# =============================================================================

class TestVisualisationComponents:

    def test_workforce_health_wheel_exists(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "WorkforceHealthWheel.tsx"
        assert path.exists(), "WorkforceHealthWheel.tsx not found"

    def test_workforce_wheel_uses_svg(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "WorkforceHealthWheel.tsx"
        content = path.read_text(encoding="utf-8")
        assert "<svg" in content

    def test_health_wheel_exports_component(self):
        path = ROOT / "executive-ui" / "src" / "components" / "visualizations" / "WorkforceHealthWheel.tsx"
        content = path.read_text(encoding="utf-8")
        assert "export function WorkforceHealthWheel" in content


# =============================================================================
# 29I — UX Navigation Groups
# =============================================================================

class TestNavigationGroups:
    def test_sidebar_has_nav_groups(self):
        path = ROOT / "executive-ui" / "src" / "layout" / "Sidebar.tsx"
        content = path.read_text(encoding="utf-8")
        assert "NAV_GROUPS" in content, "Sidebar should have grouped navigation (NAV_GROUPS)"

    def test_sidebar_has_executive_group(self):
        path = ROOT / "executive-ui" / "src" / "layout" / "Sidebar.tsx"
        content = path.read_text(encoding="utf-8")
        assert "Executive" in content or "executive" in content

    def test_sidebar_has_governance_group(self):
        path = ROOT / "executive-ui" / "src" / "layout" / "Sidebar.tsx"
        content = path.read_text(encoding="utf-8")
        assert "Governance" in content or "governance" in content

    def test_sidebar_has_data_group(self):
        path = ROOT / "executive-ui" / "src" / "layout" / "Sidebar.tsx"
        content = path.read_text(encoding="utf-8")
        assert "Data" in content or "data" in content.lower()
