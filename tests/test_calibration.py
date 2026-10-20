"""
test_calibration.py
Phase 15 — CalibrationEngine unit tests.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pytest

from backend.core.calibration_engine import (
    CalibrationEngine,
    CalibrationQuality,
    CalibrationReport,
    evaluate_calibration,
    _brier_score,
    _expected_calibration_error,
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _perfect_probs(n=500, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, 0.3, n)
    # Near-perfect: add tiny noise
    p = y.astype(float) * 0.95 + (1 - y.astype(float)) * 0.05
    return y, p


def _random_probs(n=500, seed=1):
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, 0.3, n)
    p = rng.uniform(0, 1, n)
    return y, p


def _overconfident_probs(n=500, seed=2):
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, 0.2, n)
    p = np.clip(y.astype(float) * 0.9 + rng.uniform(0.4, 0.8, n) * (1 - y.astype(float)), 0.01, 0.99)
    return y, p


# ─── brier score ─────────────────────────────────────────────────────────────

def test_brier_perfect():
    y = np.array([1, 0, 1, 0])
    p = np.array([1.0, 0.0, 1.0, 0.0])
    assert _brier_score(y, p) == pytest.approx(0.0, abs=1e-9)


def test_brier_random():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.5, 0.5, 0.5, 0.5])
    assert _brier_score(y, p) == pytest.approx(0.25, abs=1e-9)


def test_brier_worst():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.0, 1.0, 0.0, 1.0])
    assert _brier_score(y, p) == pytest.approx(1.0, abs=1e-9)


# ─── ece ─────────────────────────────────────────────────────────────────────

def test_ece_returns_tuple():
    y, p = _perfect_probs()
    ece, bins = _expected_calibration_error(y, p)
    assert isinstance(ece, float)
    assert isinstance(bins, list)


def test_ece_perfect_is_low():
    y, p = _perfect_probs()
    ece, _ = _expected_calibration_error(y, p)
    assert ece < 0.15


def test_ece_random_is_high():
    y, p = _random_probs()
    ece, _ = _expected_calibration_error(y, p)
    assert ece > 0.0


# ─── CalibrationEngine ───────────────────────────────────────────────────────

class TestCalibrationEngine:
    def test_none_inputs_returns_not_evaluated(self):
        r = CalibrationEngine().evaluate(None, None)
        assert r.quality == CalibrationQuality.NOT_EVALUATED
        assert r.brier_score is None
        assert r.ece is None

    def test_too_few_samples_returns_not_evaluated(self):
        y = np.array([1, 0, 1])
        p = np.array([0.8, 0.2, 0.7])
        r = CalibrationEngine().evaluate(y, p)
        assert r.quality == CalibrationQuality.NOT_EVALUATED

    def test_single_class_returns_not_evaluated(self):
        y = np.zeros(100)
        p = np.random.uniform(0, 1, 100)
        r = CalibrationEngine().evaluate(y, p)
        assert r.quality == CalibrationQuality.NOT_EVALUATED

    def test_good_calibration_detected(self):
        y, p = _perfect_probs(n=1000)
        r = CalibrationEngine().evaluate(y, p)
        assert r.quality in (CalibrationQuality.GOOD, CalibrationQuality.MODERATE)
        assert r.brier_score is not None
        assert r.brier_score < 0.20

    def test_poor_calibration_detected(self):
        y, p = _random_probs(n=1000)
        r = CalibrationEngine().evaluate(y, p)
        assert r.quality == CalibrationQuality.POOR

    def test_overconfidence_flag(self):
        y, p = _overconfident_probs(n=1000)
        r = CalibrationEngine().evaluate(y, p)
        # high predicted probs relative to base rate
        assert isinstance(r.overconfident, bool)

    def test_report_has_reliability_bins(self):
        y, p = _random_probs(n=500)
        r = CalibrationEngine().evaluate(y, p)
        assert len(r.reliability_bins) > 0

    def test_report_n_samples(self):
        y, p = _random_probs(n=200)
        r = CalibrationEngine().evaluate(y, p)
        assert r.n_samples == 200

    def test_brier_and_ece_are_in_range(self):
        y, p = _random_probs(n=300)
        r = CalibrationEngine().evaluate(y, p)
        if r.brier_score is not None:
            assert 0.0 <= r.brier_score <= 1.0
        if r.ece is not None:
            assert 0.0 <= r.ece <= 1.0

    def test_summary_non_empty(self):
        y, p = _random_probs(n=200)
        r = CalibrationEngine().evaluate(y, p)
        assert len(r.summary) > 0

    def test_convenience_wrapper(self):
        y, p = _random_probs(n=200)
        r = evaluate_calibration(y, p)
        assert isinstance(r, CalibrationReport)

    def test_caveats_for_poor_calibration(self):
        y, p = _random_probs(n=500)
        r = CalibrationEngine().evaluate(y, p)
        if r.quality == CalibrationQuality.POOR:
            assert len(r.caveats) > 0

    def test_no_exception_on_invalid_probs(self):
        y = np.array([1, 0] * 50)
        p = np.full(100, 0.5)
        r = CalibrationEngine().evaluate(y, p)
        assert isinstance(r, CalibrationReport)

    def test_mean_predicted_equals_mean_observed_for_calibrated(self):
        y, p = _perfect_probs(n=500)
        r = CalibrationEngine().evaluate(y, p)
        if r.mean_predicted_prob is not None and r.mean_observed_rate is not None:
            assert abs(r.mean_predicted_prob - r.mean_observed_rate) < 0.5


# ─── integration: confidence_governance uses calibration ─────────────────────

def test_confidence_governor_accepts_brier_and_ece():
    from backend.core.confidence_governance import ConfidenceGovernor
    ucr = ConfidenceGovernor().build(
        profiler_quality_score=80.0,
        missing_pct=0.05,
        n_rows=500,
        n_cols=20,
        routing_type="hr_attrition",
        routing_confidence_raw=0.85,
        routing_locked=False,
        has_ml_model=True,
        original_auc=0.80,
        governed_auc=0.80,
        brier_score=0.12,
        calibration_ece=0.04,
        feature_trust_score=0.85,
        feature_dominance_flag=False,
        train_test_gap=0.02,
        oof_fold_std=0.03,
    )
    assert ucr.model_reliability.score > 0.0
    assert ucr.model_reliability.score <= 1.0
    assert "AUC" in ucr.model_reliability.reason
    assert "leakage" in ucr.model_reliability.reason.lower()


def test_confidence_governor_poor_calibration_degrades_score():
    from backend.core.confidence_governance import ConfidenceGovernor
    good = ConfidenceGovernor().build(
        profiler_quality_score=80.0, missing_pct=0.05, n_rows=500, n_cols=20,
        routing_type="hr_attrition", routing_confidence_raw=0.85, routing_locked=False,
        has_ml_model=True, original_auc=0.80, governed_auc=0.80,
        brier_score=0.05, calibration_ece=0.03,
    )
    poor = ConfidenceGovernor().build(
        profiler_quality_score=80.0, missing_pct=0.05, n_rows=500, n_cols=20,
        routing_type="hr_attrition", routing_confidence_raw=0.85, routing_locked=False,
        has_ml_model=True, original_auc=0.80, governed_auc=0.80,
        brier_score=0.24, calibration_ece=0.18,
    )
    assert good.model_reliability.score > poor.model_reliability.score
