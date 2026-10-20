"""
test_no_stack_traces.py
Phase 15 — Verify no raw stack traces escape to UI layer.
All error handling in app.py must produce user-safe messages.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import re
import pytest


STACK_TRACE_PATTERNS = [
    r"Traceback \(most recent call last\)",
    r'File ".*", line \d+',
    r"^\s+raise\s",
    r"AttributeError:",
    r"KeyError:",
    r"ValueError:",
    r"TypeError:",
    r"ImportError:",
    r"ModuleNotFoundError:",
    r"ZeroDivisionError:",
    r"IndexError:",
]


def _matches_stack_trace(text: str) -> list:
    """Return list of matching patterns (empty = no stack trace)."""
    found = []
    for pattern in STACK_TRACE_PATTERNS:
        if re.search(pattern, text, re.MULTILINE):
            found.append(pattern)
    return found


# ─── backend modules must not raise to callers on bad input ──────────────────

def test_calibration_engine_does_not_raise_on_none():
    from backend.core.calibration_engine import CalibrationEngine
    r = CalibrationEngine().evaluate(None, None)
    assert r is not None


def test_calibration_engine_does_not_raise_on_bad_array():
    import numpy as np
    from backend.core.calibration_engine import CalibrationEngine
    r = CalibrationEngine().evaluate(
        y_true=np.array([1, 2, 3, "a"], dtype=object),
        y_prob=None,
    )
    assert r is not None


def test_confidence_governor_does_not_raise_on_bad_auc():
    from backend.core.confidence_governance import ConfidenceGovernor
    r = ConfidenceGovernor().build(
        profiler_quality_score=80.0,
        missing_pct=0.0,
        n_rows=500,
        n_cols=20,
        routing_type="hr_attrition",
        routing_confidence_raw=1.5,   # out of range
        routing_locked=False,
        has_ml_model=True,
        original_auc=-0.1,            # invalid
        governed_auc=2.0,             # out of range
    )
    assert r is not None
    assert 0.0 <= r.analysis_confidence.score <= 1.0


def test_insight_generator_does_not_raise_on_none_org_risk():
    from backend.core.insight_generator import InsightGenerator
    r = InsightGenerator().generate(
        dataset_type="hr_attrition",
        org_risk=None,
        model_auc=0.0,
    )
    assert r is not None
    assert isinstance(r.insights, list)


def test_report_generator_does_not_raise_on_empty_features():
    from backend.core.report_generator import ReportGenerator
    r = ReportGenerator().generate_hr_report(
        dataset_type="hr_attrition",
        dataset_subtype="",
        n_rows=100,
        n_features=0,
        data_quality_score=0.5,
        target_column=None,
        model_type="",
        auc_score=0.0,
        training_mode="Unsupervised",
        top_features=[],
        attrition_rate=None,
        risk_distribution=None,
        bias_risk_level="acceptable",
        ethical_disclaimer="Review required.",
        provenance_steps=[],
        caveats=[],
        governed_confidence=0.5,
    )
    assert r is not None
    assert r.full_text


def test_feature_trustworthiness_does_not_raise_on_empty():
    import pandas as pd
    from backend.core.feature_trustworthiness import FeatureTrustworthinessAssessor
    df = pd.DataFrame()
    r = FeatureTrustworthinessAssessor().assess(
        df=df, feature_names=[], target_col="X", feature_importances={}
    )
    assert r is not None


# ─── report text must not contain stack trace markers ────────────────────────

def test_report_full_text_no_stack_trace():
    from backend.core.report_generator import ReportGenerator
    rep = ReportGenerator().generate_hr_report(
        dataset_type="hr_attrition",
        dataset_subtype="Workforce",
        n_rows=300,
        n_features=15,
        data_quality_score=0.75,
        target_column="Attrition",
        model_type="RandomForest",
        auc_score=0.78,
        training_mode="AutoML",
        top_features=[],
        attrition_rate=0.20,
        risk_distribution={"High": 60, "Low": 240},
        bias_risk_level="acceptable",
        ethical_disclaimer="HR review.",
        provenance_steps=["Raw data", "Cleaned"],
        caveats=[],
        governed_confidence=0.73,
    )
    matches = _matches_stack_trace(rep.full_text)
    assert not matches, f"Stack trace markers in report: {matches}"


def test_insight_executive_summary_no_stack_trace():
    from backend.core.insight_generator import InsightGenerator
    from unittest.mock import MagicMock
    org = MagicMock()
    org.overall_attrition_risk   = 0.45
    org.high_risk_employees      = 20
    org.total_employees          = 100
    org.high_risk_pct            = 0.20
    org.total_financial_exposure = 200_000.0
    org.currency                 = "SAR"
    org.total_financial_exposure_usd = 200_000.0
    org.early_warning_level      = "Elevated"
    org.most_at_risk_dept        = None
    org.department_risks         = []
    org.sustainability_score     = 70.0
    org.burnout_hotspot          = None
    rep = InsightGenerator().generate(
        dataset_type="hr_attrition",
        org_risk=org,
    )
    full = rep.executive_summary + " ".join(i.body for i in rep.insights)
    matches = _matches_stack_trace(full)
    assert not matches, f"Stack trace in insight text: {matches}"


# ─── calibration engine summary must be safe ─────────────────────────────────

def test_calibration_summary_no_stack_trace():
    import numpy as np
    from backend.core.calibration_engine import CalibrationEngine
    rng = np.random.default_rng(99)
    y = rng.binomial(1, 0.3, 300)
    p = rng.uniform(0, 1, 300)
    r = CalibrationEngine().evaluate(y, p)
    matches = _matches_stack_trace(r.summary)
    assert not matches, f"Stack trace in calibration summary: {matches}"
