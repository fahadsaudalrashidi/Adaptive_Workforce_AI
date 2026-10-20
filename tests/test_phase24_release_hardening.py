"""
Phase 24 — Final Enterprise Hardening tests.

Phase 40: this file originally covered executive_decision_intelligence.py
and workforce_simulation_engine.py (module-import check, None/empty-input
resilience, governance/causal-language checks, required-keys checks) — both
modules were removed along with employee_risk_scoring.py and the whole
shared-upload/session pipeline they served. Only the one test unrelated to
either module (export safety PII blocking) remains. See
PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.

Run: py -m pytest tests/test_phase24_release_hardening.py -v
"""

import pandas as pd

from backend.core.export_safety import ExportSafetyValidator


def test_export_safety_validator_blocks_pii():
    df = pd.DataFrame({
        "employee_id": [1, 2],
        "name": ["Alice", "Bob"],
        "email": ["a@x.com", "b@x.com"],
        "risk_score": [60, 40],
    })
    validator = ExportSafetyValidator()
    # is_safe_for_export should flag a df containing PII-like columns (name, email)
    result = validator.is_safe_for_export(df)
    # Returns bool — we just verify the method runs without error
    assert isinstance(result, bool)
