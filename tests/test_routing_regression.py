"""
test_routing_regression.py
Phase 15 — Adaptive routing regression protection.
Verifies biosignal → never HR pipeline, HR → never biosignal pipeline.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
import pytest

from backend.core.dataset_contract import DatasetContract


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_hr_df(n=200, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "EmployeeID":       range(n),
        "Age":              rng.integers(22, 60, n),
        "Department":       rng.choice(["Sales","Tech","HR"], n),
        "MonthlyIncome":    rng.integers(3000, 20000, n),
        "JobSatisfaction":  rng.integers(1, 5, n),
        "YearsAtCompany":   rng.integers(0, 20, n),
        "Attrition":        rng.choice(["Yes","No"], n),
    })


def _make_biosignal_df(n=300, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / 256.0
    return pd.DataFrame({
        "timestamp": t,
        "ecg_mv":    np.sin(2 * np.pi * 1.2 * t) + rng.normal(0, 0.05, n),
        "heart_rate": rng.integers(60, 100, n).astype(float),
        "rr_interval": rng.uniform(0.6, 1.0, n),
    })


# ─── DatasetContract routing rules ───────────────────────────────────────────

def test_hr_contract_allows_attrition_prediction():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_hr_df()
    router = AdaptiveRouter()
    contract = router.route(df, "hr_data.csv")
    # HR datasets must allow attrition prediction
    assert contract.allows("attrition_prediction"), (
        f"HR dataset blocked from attrition_prediction. "
        f"dataset_type={contract.dataset_type}"
    )


def test_biosignal_contract_blocks_attrition_prediction():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_biosignal_df()
    router = AdaptiveRouter()
    contract = router.route(df, "ecg_recording.csv")
    assert contract.blocks("attrition_prediction"), (
        f"Biosignal dataset was NOT blocked from attrition_prediction. "
        f"dataset_type={contract.dataset_type}"
    )


def test_biosignal_contract_is_biosignal_flag():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_biosignal_df()
    router = AdaptiveRouter()
    contract = router.route(df, "ecg_signal.csv")
    assert contract.is_biosignal, "Biosignal contract must have is_biosignal=True"


def test_hr_contract_is_not_biosignal():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_hr_df()
    router = AdaptiveRouter()
    contract = router.route(df, "workforce.csv")
    assert not contract.is_biosignal, "HR contract must NOT have is_biosignal=True"


def test_biosignal_row_label_not_employee():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_biosignal_df()
    router = AdaptiveRouter()
    contract = router.route(df, "ecg.csv")
    label = contract.row_label().lower()
    assert "employee" not in label, (
        f"Biosignal row_label must never be 'employee', got: {contract.row_label()!r}"
    )


def test_hr_contract_row_label_is_employee_like():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_hr_df()
    router = AdaptiveRouter()
    contract = router.route(df, "employees.csv")
    label = contract.row_label().lower()
    assert any(w in label for w in ("employee", "worker", "staff", "person", "record")), (
        f"HR row_label should be employee-like, got: {contract.row_label()!r}"
    )


# ─── DatasetContract.allows / .blocks consistency ────────────────────────────

def test_allows_and_blocks_are_mutually_exclusive():
    from backend.core.adaptive_router import AdaptiveRouter
    for df, name in [(_make_hr_df(), "hr.csv"), (_make_biosignal_df(), "bio.csv")]:
        router = AdaptiveRouter()
        contract = router.route(df, name)
        for key in ["attrition_prediction", "department_stability", "biosignal_analysis"]:
            if contract.allows(key):
                assert not contract.blocks(key), f"{key} is both allowed and blocked"
            if contract.blocks(key):
                assert not contract.allows(key), f"{key} is both blocked and allowed"


def test_contract_sandbox_report_exists():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_hr_df()
    router = AdaptiveRouter()
    contract = router.route(df, "test.csv")
    assert contract.sandbox_report is not None


# ─── routing confidence ───────────────────────────────────────────────────────

def test_routing_confidence_present():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_hr_df()
    router = AdaptiveRouter()
    contract = router.route(df, "workforce.csv")
    rc = contract.routing_confidence
    assert rc is not None
    assert 0.0 <= rc.overall_confidence <= 1.0


def test_biosignal_routing_confidence_high_when_clear_signal():
    from backend.core.adaptive_router import AdaptiveRouter
    df = _make_biosignal_df()
    router = AdaptiveRouter()
    contract = router.route(df, "ecg_data.csv")
    rc = contract.routing_confidence
    # For a clearly structured biosignal file, confidence should be reasonable
    assert rc is not None and rc.overall_confidence > 0.0

# Phase 39: test_smote_not_applied_before_split (backend.core.ml_router.MLRouter)
# was removed along with ml_router.py — see
# PHASE_39_PREDICTION_REMOVAL_AND_ENTERPRISE_REBRAND_REPORT.md.
