"""
Phase 6 — Ethical AI (fairness/bias audit) engine tests.

Covers the confirmed regression from ETHICAL_AI_ENGINE_INVESTIGATION.md §5b:
running a real bias audit against the platform's actual test_employee_data.csv
fixture (Age: 34 distinct values across 200 rows) produced a disparity ratio
of 428,600,000x, labeled "CRITICAL" — because Age was grouped by raw unique
value with no bucketing and no minimum-group-size floor, and a handful of
resulting 5-10-person groups happened to have zero attrition by chance,
blowing up the ratio at the near-zero epsilon floor.

Two independent guards are tested here:
  1. Granularity gating (_bucket_or_skip_for_disparity) — high-cardinality
     numeric attributes are bucketed into quantile bands before comparison;
     high-cardinality non-numeric attributes are skipped with a disclosed
     note; low-cardinality attributes proceed directly (representation_warning
     is consulted downstream instead — see test_min_group_size_exclusion).
  2. Minimum-group-size floor (_MIN_GROUP_SIZE_FOR_DISPARITY = 20) — any
     individual group below this size is excluded from a disparity
     computation, never silently included with a possibly-zero rate.

Also covers a true-negative (genuinely fair data -> low/acceptable risk) and
a true-positive (genuinely disparate data, realistic group sizes -> real
risk correctly flagged) case, so this suite cannot degenerate into a module
that never triggers.

Run: py -m pytest tests/test_ethical_ai.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backend.core.ethical_ai import (
    EthicalAIEngine,
    _MAX_DISTINCT_VALUES_FOR_RAW_GROUPING,
    _MIN_GROUP_SIZE_FOR_DISPARITY,
    bias_audit_to_dict,
    detect_attrition_target_column,
    ethical_report_to_dict,
)

_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "test_employee_data.csv"


@pytest.fixture(scope="module")
def real_employee_df() -> pd.DataFrame:
    assert _FIXTURE_PATH.exists(), f"expected fixture at {_FIXTURE_PATH}"
    return pd.read_csv(_FIXTURE_PATH)


@pytest.fixture
def engine() -> EthicalAIEngine:
    return EthicalAIEngine()


# ── 1. Age-bucketing regression test (the confirmed bug, reproduced + fixed) ──

def test_age_has_high_cardinality_confirming_the_bug_precondition(real_employee_df):
    """Sanity precondition: Age must genuinely have more distinct values than
    the raw-grouping threshold, or this regression test would prove nothing."""
    n_distinct = real_employee_df["Age"].dropna().nunique()
    assert n_distinct > _MAX_DISTINCT_VALUES_FOR_RAW_GROUPING
    assert n_distinct == 34  # exact value confirmed during investigation


def test_age_disparity_no_longer_fabricated(engine, real_employee_df):
    """The headline regression assertion: disparity ratio for Age must be a
    small, plausible number, never anywhere close to the fabricated
    428,600,000x the pre-fix code produced against this exact fixture."""
    result = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    age_metric = next(m for m in result.fairness_metrics if m.attribute_column == "Age")

    assert age_metric.was_bucketed is True
    # Generous sanity bound — any real bucketed HR attrition disparity is a
    # small multiple, not millions. This alone would have caught the bug.
    assert age_metric.disparity_ratio < 20.0
    # Tighter check against the actual observed value at fix time.
    assert age_metric.disparity_ratio == pytest.approx(1.3815, abs=0.05)


def test_age_disparity_matches_independent_hand_computation(engine, real_employee_df):
    """Independently rebuild the bucketed group rates using pandas directly
    (not calling into the engine's own bucketing function) and assert the
    engine's output matches exactly — a true hand-computed check, not a
    circular one."""
    result = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    age_metric = next(m for m in result.fairness_metrics if m.attribute_column == "Age")

    buckets = pd.qcut(real_employee_df["Age"], q=5, duplicates="drop")
    work = pd.DataFrame({"_bucket": buckets, "_attr": real_employee_df["Attrition"]})
    expected_rates = {}
    for bucket_val, grp in work.groupby("_bucket", observed=True):
        expected_rates[str(bucket_val)] = round(float((grp["_attr"] == "Yes").sum()) / len(grp), 4)
    expected_disparity = round(max(expected_rates.values()) / max(min(expected_rates.values()), 1e-9), 4)

    assert age_metric.group_rates == expected_rates
    assert age_metric.disparity_ratio == expected_disparity


def test_age_bucketing_note_discloses_what_happened(engine, real_employee_df):
    """The bucketing must be disclosed, never silent."""
    result = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    assert any(
        "Age" in n and "bucketed" in n.lower() for n in result.granularity_notes
    )


def test_overall_risk_level_no_longer_forced_critical_by_fabricated_age_ratio(engine, real_employee_df):
    """Before the fix, Age's fabricated 428,600,000x ratio single-handedly
    forced overall_risk_level to "critical" via the worst-single-metric
    rule. The ratio-based classification is intentionally left in place
    post-fix (see module docstring) — but it must now be driven by a real,
    bounded number, not an artifact."""
    result = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    age_metric = next(m for m in result.fairness_metrics if m.attribute_column == "Age")
    assert age_metric.disparity_ratio < 20.0  # re-assert the bound feeding overall_risk_level


# ── 2. Minimum-group-size floor ─────────────────────────────────────────────

def test_min_group_size_exclusion(engine):
    """A protected attribute with a tiny subgroup (below the floor) must
    have that subgroup excluded from the comparison — with a disclosed
    "insufficient sample size" note — while larger groups are still
    compared normally."""
    df = pd.DataFrame({
        "Gender": ["Male"] * 100 + ["Female"] * 100 + ["Other"] * 3,
        "Attrition": (
            (["Yes"] * 20 + ["No"] * 80)
            + (["Yes"] * 18 + ["No"] * 82)
            + ["Yes", "No", "No"]
        ),
    })
    result = engine.audit_bias(df, target_col="Attrition", positive_label="Yes")
    metric = next(m for m in result.fairness_metrics if m.attribute_column == "Gender")

    assert "Other" not in metric.group_rates
    assert metric.group_rates == {"Male": 0.2, "Female": 0.18}
    assert metric.n_groups_excluded_small_sample == 1
    assert any(
        "Other" in n and "n=3" in n and "excluded" in n.lower()
        for n in result.granularity_notes
    )


def test_below_floor_group_never_silently_included():
    """Confirm the floor constant itself and that a group of exactly
    (floor - 1) members is excluded, while a group of exactly floor members
    is included — an off-by-one boundary check."""
    engine = EthicalAIEngine()
    n = _MIN_GROUP_SIZE_FOR_DISPARITY
    df = pd.DataFrame({
        "Gender": ["Male"] * n + ["Female"] * (n - 1),
        "Attrition": (["Yes"] * (n // 4) + ["No"] * (n - n // 4)) + (["Yes"] * 2 + ["No"] * (n - 3)),
    })
    result = engine.audit_bias(df, target_col="Attrition", positive_label="Yes")
    fairness_cols = [m.attribute_column for m in result.fairness_metrics]
    # Female (n-1 members) is below the floor -> excluded -> fewer than 2
    # comparable groups -> no metric computed for Gender at all.
    assert "Gender" not in fairness_cols
    assert any("fewer than 2 groups" in note.lower() or "excluded" in note.lower() for note in result.granularity_notes)


# ── 3. Skip (not bucket) for non-numeric high-cardinality attributes ───────

def test_high_cardinality_non_numeric_attribute_is_skipped_not_guessed(engine):
    df = pd.DataFrame({
        "Nationality": [f"Country_{i % 15}" for i in range(150)],
        "Attrition": (["Yes", "No"] * 75),
    })
    result = engine.audit_bias(df, target_col="Attrition", positive_label="Yes")
    fairness_cols = [m.attribute_column for m in result.fairness_metrics]
    assert "Nationality" not in fairness_cols
    assert any(
        "Nationality" in n and "not reliably numeric" in n for n in result.granularity_notes
    )


# ── 4. True-negative: genuinely fair data -> low/acceptable risk ───────────

def test_genuinely_fair_data_yields_low_risk(engine):
    """Near-equal selection rates across two large, well-sized groups must
    NOT be flagged as high/critical risk — this is the true-negative case."""
    rng = np.random.default_rng(11)
    male = ["Yes"] * 30 + ["No"] * 170
    female = ["Yes"] * 32 + ["No"] * 168
    rng.shuffle(male)
    rng.shuffle(female)
    df = pd.DataFrame({
        "Gender": ["Male"] * 200 + ["Female"] * 200,
        "Attrition": male + female,
    })
    result = engine.audit_bias(df, target_col="Attrition", positive_label="Yes")
    metric = next(m for m in result.fairness_metrics if m.attribute_column == "Gender")

    expected_disparity = round(max(0.15, 0.16) / min(0.15, 0.16), 4)
    assert metric.disparity_ratio == pytest.approx(expected_disparity)
    assert metric.risk_level in {"acceptable", "low", "medium"}
    assert result.overall_risk_level in {"acceptable", "low", "medium"}
    # A ~1pp gap on n=200 groups should not be statistically significant.
    assert metric.statistically_significant is False


# ── 5. True-positive: genuinely disparate data, realistic group sizes ──────

def test_genuinely_disparate_data_is_correctly_flagged(engine):
    """A real, large disparity (not a small-sample artifact) must still be
    caught — confirms the fix didn't neuter the module into never
    triggering."""
    rng = np.random.default_rng(3)
    male = ["Yes"] * 50 + ["No"] * 150     # 25% attrition, n=200
    female = ["Yes"] * 10 + ["No"] * 190   # 5% attrition, n=200
    rng.shuffle(male)
    rng.shuffle(female)
    df = pd.DataFrame({
        "Gender": ["Male"] * 200 + ["Female"] * 200,
        "Attrition": male + female,
    })
    result = engine.audit_bias(df, target_col="Attrition", positive_label="Yes")
    metric = next(m for m in result.fairness_metrics if m.attribute_column == "Gender")

    assert metric.group_rates == {"Male": 0.25, "Female": 0.05}
    assert metric.disparity_ratio == pytest.approx(5.0)
    assert metric.risk_level == "critical"
    assert result.overall_risk_level == "critical"
    assert result.bias_detected is True
    assert result.audit_passed is False
    # A 5x disparity on n=200 groups should be clearly statistically significant.
    assert metric.statistically_significant is True
    assert metric.p_value < 0.001


# ── 6. No protected attributes -> honest not-applicable result ─────────────

def test_no_protected_attributes_detected_is_honest_not_fabricated(engine):
    df = pd.DataFrame({
        "EmployeeID": [f"E{i}" for i in range(60)],
        "Department": ["Sales", "Finance"] * 30,
        "OverTime": ["Yes", "No"] * 30,
    })
    result = engine.audit_bias(df, target_col="OverTime", positive_label="Yes")
    assert result.protected_attributes == []
    assert result.fairness_metrics == []
    assert "no protected attributes" in result.audit_summary.lower()


# ── 7. Serialization ────────────────────────────────────────────────────────

def test_bias_audit_to_dict_is_json_safe_and_complete(engine, real_employee_df):
    import json
    result = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    d = bias_audit_to_dict(result)
    json.dumps(d)  # must not raise
    assert "granularity_notes" in d
    assert isinstance(d["fairness_metrics"], list)
    for m in d["fairness_metrics"]:
        assert "was_bucketed" in m
        assert "p_value" in m
        assert "statistically_significant" in m


def test_detect_attrition_target_column_finds_real_column(real_employee_df):
    col, positive = detect_attrition_target_column(real_employee_df)
    assert col == "Attrition"
    assert positive == "Yes"


def test_detect_attrition_target_column_none_when_absent():
    df = pd.read_csv(Path(__file__).resolve().parent.parent / "messy_test_data.csv")
    col, positive = detect_attrition_target_column(df)
    assert col is None
    assert positive is None


def test_generate_ethical_report_caveats_non_significant_critical_result(engine, real_employee_df):
    """test_employee_data.csv's Age metric is ratio-critical but NOT
    statistically significant (p=0.52) — the blocking-issue TEXT must say
    so explicitly, not just expose it as a separate field the caller might
    not render. The ratio-based risk_level/overall_status classification
    itself is intentionally left unchanged (documented design choice)."""
    audit = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    assert audit.overall_risk_level == "critical"
    report = engine.generate_ethical_report(audit, [])
    assert report.overall_ethical_status == "Fail"
    assert any("CAVEAT" in b and "did NOT reach" in b for b in report.blocking_issues)


def test_generate_ethical_report_no_caveat_when_genuinely_significant(engine):
    """A real, significant disparity must NOT carry the non-significance
    caveat — the caveat is specifically for the non-significant case."""
    rng = np.random.default_rng(3)
    male = ["Yes"] * 50 + ["No"] * 150
    female = ["Yes"] * 10 + ["No"] * 190
    rng.shuffle(male); rng.shuffle(female)
    df = pd.DataFrame({"Gender": ["Male"] * 200 + ["Female"] * 200, "Attrition": male + female})
    audit = engine.audit_bias(df, target_col="Attrition", positive_label="Yes")
    report = engine.generate_ethical_report(audit, [])
    assert not any("CAVEAT" in b for b in report.blocking_issues)


def test_ethical_report_to_dict_is_json_safe(engine, real_employee_df):
    import json
    audit = engine.audit_bias(real_employee_df, target_col="Attrition", positive_label="Yes")
    gov = engine.govern_prediction(
        "attrition", raw_confidence=0.75, n_samples=len(real_employee_df),
        data_quality_score=0.9, auc_score=0.72, protected_bias_risk=audit.overall_risk_level,
    )
    report = engine.generate_ethical_report(audit, [gov])
    d = ethical_report_to_dict(report)
    json.dumps(d)  # must not raise
    assert d["overall_ethical_status"] in {"Pass", "Conditional", "Fail"}
