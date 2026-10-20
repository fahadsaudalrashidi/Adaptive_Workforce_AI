"""
test_construct_evidence.py
Phase 15 — Burnout/construct evidence governance.
BurnoutRisk must be None (not 0.0) when evidence is insufficient.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
import pytest


# ─── helpers ─────────────────────────────────────────────────────────────────

def _score_df(df, probs=None, currency="SAR"):
    from backend.core.risk_intelligence import score_individuals
    from unittest.mock import MagicMock
    sem_map = MagicMock()
    sem_map.salary_col = "MonthlyIncome" if "MonthlyIncome" in df.columns else None
    sem_map.tenure_col = "YearsAtCompany" if "YearsAtCompany" in df.columns else None
    if probs is None:
        rng = np.random.default_rng(0)
        probs = rng.uniform(0.1, 0.9, len(df))
    return score_individuals(df, probs, sem_map, currency=currency)


# ─── BurnoutRisk: None when no evidence ─────────────────────────────────────

def test_burnout_risk_none_when_no_burnout_column():
    rng = np.random.default_rng(0)
    n = 100
    df = pd.DataFrame({
        "Age":            rng.integers(25, 55, n),
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 15, n),
        "JobSatisfaction": rng.integers(1, 5, n),
    })
    risks = _score_df(df)
    burnout_values = [r.burnout_risk for r in risks]
    # Must be None (no burnout column → no fake zero)
    assert all(v is None for v in burnout_values), (
        f"BurnoutRisk should be None when no burnout column present. "
        f"Got non-None values: {[v for v in burnout_values if v is not None][:5]}"
    )


def test_burnout_risk_not_zero_when_no_evidence():
    rng = np.random.default_rng(1)
    n = 80
    df = pd.DataFrame({
        "EmployeeID": range(n),
        "Age": rng.integers(22, 60, n),
    })
    risks = _score_df(df)
    zero_burnouts = [r.burnout_risk for r in risks if r.burnout_risk == 0.0]
    assert len(zero_burnouts) == 0, (
        f"BurnoutRisk must never be 0.0 when there is no evidence. "
        f"Got {len(zero_burnouts)} zero values."
    )


def test_burnout_risk_present_when_evidence_exists():
    rng = np.random.default_rng(2)
    n = 150
    df = pd.DataFrame({
        "Age":                   rng.integers(25, 55, n),
        "MonthlyIncome":         rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany":        rng.integers(1, 15, n),
        "BurnoutRiskComposite":  rng.uniform(0.1, 0.9, n),  # engineered burnout col
    })
    risks = _score_df(df)
    # At least some should have a non-None burnout risk
    non_none = [r for r in risks if r.burnout_risk is not None]
    assert len(non_none) > 0, "BurnoutRisk should be populated when BurnoutRiskComposite column present"


# ─── EngagementRisk: None when no evidence ───────────────────────────────────

def test_engagement_risk_none_when_no_engagement_column():
    rng = np.random.default_rng(3)
    n = 100
    df = pd.DataFrame({
        "Age":            rng.integers(25, 55, n),
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
    })
    risks = _score_df(df)
    engagement_values = [r.engagement_risk for r in risks]
    assert all(v is None for v in engagement_values), (
        "EngagementRisk should be None when no engagement column present"
    )


# ─── Confidence governor acknowledges missing evidence ───────────────────────

def test_confidence_governor_caveat_for_missing_burnout():
    from backend.core.confidence_governance import ConfidenceGovernor
    ucr = ConfidenceGovernor().build(
        profiler_quality_score=80.0,
        missing_pct=0.05,
        n_rows=300,
        n_cols=15,
        routing_type="hr_attrition",
        routing_confidence_raw=0.85,
        routing_locked=False,
        has_ml_model=True,
        original_auc=0.78,
        governed_auc=0.78,
        has_burnout_evidence=False,
        has_engagement_evidence=False,
    )
    caveats_text = " ".join(ucr.caveats).lower()
    assert "burnout" in caveats_text, "Missing burnout evidence should add a caveat"


def test_confidence_governor_no_caveat_when_evidence_present():
    from backend.core.confidence_governance import ConfidenceGovernor
    ucr = ConfidenceGovernor().build(
        profiler_quality_score=80.0,
        missing_pct=0.05,
        n_rows=300,
        n_cols=15,
        routing_type="hr_attrition",
        routing_confidence_raw=0.85,
        routing_locked=False,
        has_ml_model=True,
        original_auc=0.78,
        governed_auc=0.78,
        has_burnout_evidence=True,
        has_engagement_evidence=True,
    )
    burnout_caveats = [c for c in ucr.caveats if "burnout" in c.lower()]
    assert len(burnout_caveats) == 0, "No burnout caveat should appear when evidence is present"


# ─── IndividualRisk dataclass has correct None defaults ──────────────────────

def test_individual_risk_burnout_is_none_by_default():
    from backend.core.risk_intelligence import IndividualRisk
    import dataclasses
    fields = {f.name: f for f in dataclasses.fields(IndividualRisk)}
    assert "burnout_risk" in fields
    # Default factory or default should be None
    default = fields["burnout_risk"].default
    default_factory = fields["burnout_risk"].default_factory
    # Either the field default is None or there's no default (set explicitly)
    assert default is None or default is dataclasses.MISSING, (
        f"IndividualRisk.burnout_risk default should be None, got {default!r}"
    )
