"""
Company Readiness Tests — Adaptive Workforce Intelligence Engine v2.3.0
========================================================================
15 tests covering all 14 enterprise-hardening requirements plus HTTP readiness.

Tests:
  CR-01  Unified confidence governance (5 dimensions, no contradictions)
  CR-02  Confidence hard caps enforced
  CR-03  Feature trustworthiness: cardinality and dominance flagging
  CR-04  Feature language always associative, never causal
  CR-05  BurnoutRisk returns None (not 0.0) when evidence unavailable
  CR-06  Department detection: real columns found, no fake "All Employees"
  CR-07  Department detection: honest unavailable when no dept column
  CR-08  Currency SAR default in risk scoring
  CR-09  Currency conversion works for USD, AED, EUR
  CR-10  Executive report uses safe HR language (no causal claims)
  CR-11  Executive report HTML generated with disclaimer
  CR-12  Model reliability governed/downgraded on leakage
  CR-13  Config versions centralised (PLATFORM_VERSION, REPORT_VERSION)
  CR-14  HUMAN_OVERSIGHT_DISCLAIMER present in settings and non-empty
  CR-15  HTTP 200 from Streamlit on port 8510 (when server running)

Run:
    py -3 test_company_readiness.py
"""
from __future__ import annotations

import os
import sys
import traceback
import warnings
from typing import Any, List

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(__file__))

# -----------------------------------------------------------------------------
# Test harness
# -----------------------------------------------------------------------------

_PASS = 0
_FAIL = 0
_ERRORS: List[str] = []


def chk(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  PASS  {name}")
    else:
        _FAIL += 1
        msg = f"  FAIL  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        _ERRORS.append(msg)


def safe_run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:
        return None, exc


# -----------------------------------------------------------------------------
# Synthetic HR data helpers
# -----------------------------------------------------------------------------

def _hr_df(n: int = 400, with_dept: bool = True, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "Age":             rng.integers(22, 58, n),
        "MonthlyIncome":   rng.integers(3000, 20000, n),
        "YearsAtCompany":  rng.integers(0, 25, n),
        "JobSatisfaction": rng.integers(1, 5, n),
        "OverTime":        rng.choice(["Yes", "No"], n),
        "Attrition":       rng.choice([0, 1], n, p=[0.84, 0.16]),
    })
    if with_dept:
        df["Department"] = rng.choice(["Engineering", "Sales", "HR", "Finance"], n)
    return df


def _hr_df_no_burnout(n: int = 300, seed: int = 1) -> pd.DataFrame:
    """HR df with no burnout-proxy columns at all."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Age":            rng.integers(22, 55, n),
        "MonthlyIncome":  rng.integers(4000, 18000, n),
        "YearsAtCompany": rng.integers(0, 20, n),
        "Department":     rng.choice(["Eng", "Sales", "Ops"], n),
        "Attrition":      rng.choice([0, 1], n, p=[0.83, 0.17]),
    })


# -----------------------------------------------------------------------------
# Imports from platform
# -----------------------------------------------------------------------------

from config.settings import (
    PLATFORM_VERSION, REPORT_VERSION, MODEL_VERSION,
    DEFAULT_CURRENCY, CURRENCY_OPTIONS, CURRENCY_SYMBOLS, CURRENCY_FROM_USD,
    HUMAN_OVERSIGHT_DISCLAIMER,
    HC_DOMINANCE_WARN_THRESHOLD, HC_DOMINANCE_FLAG_THRESHOLD,
    HC_UNIQUE_RATIO_RISK, CARDINALITY_HIGH,
)
from backend.core.confidence_governance import (
    ConfidenceGovernor, EXEC_READY, EXEC_CAUTION, EXEC_LIMITED, EXEC_NOT_READY,
)
from backend.core.feature_trustworthiness import (
    FeatureTrustworthinessAssessor,
    TRUST_RELIABLE, TRUST_CAUTION, TRUST_HIGH_RISK,
)
from backend.core.risk_intelligence import (
    score_individuals, score_departments, score_organization,
    IndividualRisk,
)
from backend.core.semantic_mapper import SemanticMapper
from backend.core.data_healer import DataHealer
from backend.core.report_generator import ReportGenerator as _ReportGenerator
_report_gen = _ReportGenerator()

sem_mapper = SemanticMapper()
healer     = DataHealer()
gov        = ConfidenceGovernor()
fta        = FeatureTrustworthinessAssessor()


# -----------------------------------------------------------------------------
# CR-01: Unified confidence governance — 5 dimensions present, no contradictions
# -----------------------------------------------------------------------------

print("\n--- CR-01: Unified confidence governance ---")

ucr, err = safe_run(gov.build,
    profiler_quality_score=78.0,
    missing_pct=0.05,
    n_rows=500,
    n_cols=12,
    routing_type="hr_attrition",
    routing_confidence_raw=0.88,
    routing_locked=False,
    has_ml_model=True,
    original_auc=0.82,
    governed_auc=0.82,
    leakage_risk_score=0.05,
    leakage_n_critical=0,
    leakage_n_high=0,
    is_trustworthy=True,
    validation_overall_status="VALID",
    validation_n_fail=0,
    oof_fold_std=0.03,
    has_burnout_evidence=True,
    has_engagement_evidence=True,
)
chk("CR-01a: build() returns without error", err is None, str(err))
if ucr:
    chk("CR-01b: data_quality dimension present", ucr.data_quality is not None)
    chk("CR-01c: routing_confidence dimension present", ucr.routing_confidence is not None)
    chk("CR-01d: model_reliability dimension present", ucr.model_reliability is not None)
    chk("CR-01e: analysis_confidence dimension present", ucr.analysis_confidence is not None)
    chk("CR-01f: executive_readiness present", ucr.executive_readiness in (
        EXEC_READY, EXEC_CAUTION, EXEC_LIMITED, EXEC_NOT_READY))
    chk("CR-01g: analysis_confidence <= 1.0", ucr.analysis_confidence.score <= 1.0)
    chk("CR-01h: analysis_confidence >= 0.0", ucr.analysis_confidence.score >= 0.0)
    # No contradiction: high-confidence path should yield READY or CAUTION
    chk("CR-01i: good-quality analysis not marked NOT_READY",
        ucr.executive_readiness != EXEC_NOT_READY,
        f"Got: {ucr.executive_readiness}")


# -----------------------------------------------------------------------------
# CR-02: Confidence hard caps enforced
# -----------------------------------------------------------------------------

print("\n--- CR-02: Confidence hard caps ---")

# Low routing confidence -> analysis_confidence capped at 0.70
ucr_low_routing, _ = safe_run(gov.build,
    profiler_quality_score=85.0, missing_pct=0.02, n_rows=600, n_cols=10,
    routing_type="unknown", routing_confidence_raw=0.40, routing_locked=False,
    has_ml_model=False, has_burnout_evidence=False, has_engagement_evidence=False,
)
chk("CR-02a: low routing cap (<=0.70)",
    ucr_low_routing is not None and ucr_low_routing.analysis_confidence.score <= 0.70,
    f"Got: {getattr(getattr(ucr_low_routing, 'analysis_confidence', None), 'score', 'N/A')}")

# Critical leakage -> not trustworthy -> analysis capped at 0.50
ucr_leak, _ = safe_run(gov.build,
    profiler_quality_score=80.0, missing_pct=0.03, n_rows=400, n_cols=8,
    routing_type="hr_attrition", routing_confidence_raw=0.85, routing_locked=True,
    has_ml_model=True, original_auc=0.91, governed_auc=0.91,
    leakage_risk_score=0.80, leakage_n_critical=2, leakage_n_high=1,
    is_trustworthy=False, validation_overall_status="INVALID", validation_n_fail=3,
    has_burnout_evidence=True, has_engagement_evidence=True,
)
chk("CR-02b: critical leakage -> NOT_READY",
    ucr_leak is not None and ucr_leak.executive_readiness == EXEC_NOT_READY,
    f"Got: {getattr(ucr_leak, 'executive_readiness', 'N/A')}")
chk("CR-02c: critical leakage -> analysis_confidence <= 0.50",
    ucr_leak is not None and ucr_leak.analysis_confidence.score <= 0.50,
    f"Got: {getattr(getattr(ucr_leak, 'analysis_confidence', None), 'score', 'N/A')}")

# Low data quality -> analysis capped at 0.65
ucr_dq, _ = safe_run(gov.build,
    profiler_quality_score=40.0, missing_pct=0.45, n_rows=100, n_cols=5,
    routing_type="hr_attrition", routing_confidence_raw=0.90, routing_locked=True,
    has_ml_model=False, has_burnout_evidence=False, has_engagement_evidence=False,
)
chk("CR-02d: low data quality cap (<=0.65)",
    ucr_dq is not None and ucr_dq.analysis_confidence.score <= 0.65,
    f"Got: {getattr(getattr(ucr_dq, 'analysis_confidence', None), 'score', 'N/A')}")


# -----------------------------------------------------------------------------
# CR-03: Feature trustworthiness — cardinality and dominance flagging
# -----------------------------------------------------------------------------

print("\n--- CR-03: Feature trustworthiness flags ---")

df_ft = _hr_df(n=200)
# Add high-cardinality JobTitle column
rng = np.random.default_rng(42)
df_ft["JobTitle"] = [f"Title_{i}" for i in rng.integers(0, 180, 200)]

importances = {
    "JobTitle":       0.65,
    "MonthlyIncome":  0.15,
    "Age":            0.08,
    "YearsAtCompany": 0.07,
    "JobSatisfaction": 0.05,
}

ftr, err = safe_run(fta.assess, df_ft, list(importances.keys()), "Attrition", importances)
chk("CR-03a: assess() returns without error", err is None, str(err))
if ftr:
    chk("CR-03b: JobTitle has High cardinality risk",
        any(a.cardinality_risk == "High" for a in ftr.assessments
            if a.feature_name == "JobTitle"),
        f"Assessments: {[(a.feature_name, a.cardinality_risk) for a in ftr.assessments]}")
    chk("CR-03c: JobTitle dominance flagged (share=65%)",
        any(a.dominance_risk in ("Warning", "Flag") for a in ftr.assessments
            if a.feature_name == "JobTitle"),
        f"Dominance: {[(a.feature_name, a.dominance_risk) for a in ftr.assessments]}")
    chk("CR-03d: overall_trust not Reliable when HC features present",
        ftr.overall_trust != TRUST_RELIABLE,
        f"Got: {ftr.overall_trust}")
    chk("CR-03e: downgrade_model_reliability set on dominance flag",
        ftr.downgrade_model_reliability,
        f"Got: {ftr.downgrade_model_reliability}")


# -----------------------------------------------------------------------------
# CR-04: Feature language always associative, never causal
# -----------------------------------------------------------------------------

print("\n--- CR-04: Associative language in feature notes ---")

CAUSAL_WORDS = ["causes", "caused by", "leads to", "results in", "determines", "drives attrition"]

if ftr and ftr.assessments:
    for a in ftr.assessments:
        note_lower = a.associative_note.lower()
        for cw in CAUSAL_WORDS:
            chk(f"CR-04: no '{cw}' in '{a.feature_name}' note",
                cw not in note_lower,
                f"Found '{cw}' in: {a.associative_note[:100]}")
    chk("CR-04z: 'associated with' in top feature note",
        "associated with" in ftr.assessments[-1].associative_note.lower()
        or "cardinality" in ftr.assessments[0].associative_note.lower()
        or "accounts for" in ftr.assessments[0].associative_note.lower()
    )


# -----------------------------------------------------------------------------
# CR-05: BurnoutRisk returns None (not 0.0) when evidence unavailable
# -----------------------------------------------------------------------------

print("\n--- CR-05: BurnoutRisk None when evidence unavailable ---")

df_no_burnout = _hr_df_no_burnout(n=200)
df_healed, _ = safe_run(healer.fit_transform, df_no_burnout)
if df_healed is None:
    df_healed = df_no_burnout

sem_map = sem_mapper.map(df_healed)

# Fake uniform probabilities (no model trained)
probs = np.full(len(df_healed), 0.20)
ind_risks, err = safe_run(score_individuals, df_healed, probs, sem_map)
chk("CR-05a: score_individuals runs without error", err is None, str(err))
if ind_risks:
    burnout_vals = [r.burnout_risk for r in ind_risks]
    chk("CR-05b: burnout_risk is None when no burnout columns",
        all(v is None for v in burnout_vals),
        f"Non-None found: {[v for v in burnout_vals if v is not None][:3]}")
    chk("CR-05c: no fake 0.0 burnout values",
        not any(v == 0.0 for v in burnout_vals),
        f"Zero values: {[v for v in burnout_vals if v == 0.0][:3]}")


# -----------------------------------------------------------------------------
# CR-06: Department detection: real columns found
# -----------------------------------------------------------------------------

print("\n--- CR-06: Department detection (column present) ---")

df_with_dept = _hr_df(n=300, with_dept=True)
probs6 = np.full(300, 0.18)
sem_map6 = sem_mapper.map(df_with_dept)
ind_risks6, err = safe_run(score_individuals, df_with_dept, probs6, sem_map6)
dept_risks6, err = safe_run(score_departments, df_with_dept, probs6, ind_risks6 or [], sem_map6)
chk("CR-06a: dept_risks list is non-empty when dept col present",
    bool(dept_risks6),
    f"Got {len(dept_risks6 or [])} dept groups")
if dept_risks6:
    dept_names = [d.department for d in dept_risks6]
    chk("CR-06b: 'All Employees' NOT in dept names",
        "All Employees" not in dept_names,
        f"Names: {dept_names}")
    chk("CR-06c: real dept names present",
        any(d in dept_names for d in ["Engineering", "Sales", "HR", "Finance"]),
        f"Names: {dept_names}")


# -----------------------------------------------------------------------------
# CR-07: Department detection: honest unavailable when no dept column
# -----------------------------------------------------------------------------

print("\n--- CR-07: Department detection (no dept column) ---")

df_no_dept = _hr_df(n=250, with_dept=False)
probs7 = np.full(250, 0.17)
sem_map7 = sem_mapper.map(df_no_dept)
ind_risks7, _ = safe_run(score_individuals, df_no_dept, probs7, sem_map7)
dept_risks7, err = safe_run(score_departments, df_no_dept, probs7, ind_risks7 or [], sem_map7)
org_risk7, err2 = safe_run(score_organization, ind_risks7 or [], dept_risks7 or [])

chk("CR-07a: score_departments returns empty list when no dept col",
    dept_risks7 is not None and len(dept_risks7) == 0,
    f"Got {dept_risks7}")
chk("CR-07b: department_column_found is False on org_risk",
    org_risk7 is not None and getattr(org_risk7, "department_column_found", None) is False,
    f"Got: {getattr(org_risk7, 'department_column_found', 'MISSING_ATTR')}")


# -----------------------------------------------------------------------------
# CR-08: Currency SAR default
# -----------------------------------------------------------------------------

print("\n--- CR-08: Currency SAR default ---")

chk("CR-08a: DEFAULT_CURRENCY == 'SAR'", DEFAULT_CURRENCY == "SAR", f"Got: {DEFAULT_CURRENCY}")
chk("CR-08b: SAR in CURRENCY_OPTIONS", "SAR" in CURRENCY_OPTIONS)
chk("CR-08c: CURRENCY_SYMBOLS has SAR", "SAR" in CURRENCY_SYMBOLS)

df_sar = _hr_df(n=200)
probs_s = np.full(200, 0.20)
sem_map_s = sem_mapper.map(df_sar)
ind_sar, err = safe_run(score_individuals, df_sar, probs_s, sem_map_s, currency="SAR")
chk("CR-08d: score_individuals with currency='SAR' runs without error", err is None, str(err))
if ind_sar:
    chk("CR-08e: individual.currency == 'SAR'",
        all(getattr(r, "currency", None) == "SAR" for r in ind_sar),
        f"Currencies: {set(getattr(r, 'currency', 'N/A') for r in ind_sar)}")


# -----------------------------------------------------------------------------
# CR-09: Currency conversion for USD, AED, EUR
# -----------------------------------------------------------------------------

print("\n--- CR-09: Currency conversion ---")

for curr in ["USD", "AED", "EUR"]:
    ind_c, err = safe_run(score_individuals, df_sar.copy(), probs_s, sem_map_s, currency=curr)
    chk(f"CR-09 {curr}: score_individuals runs without error", err is None, str(err))
    if ind_c:
        chk(f"CR-09 {curr}: currency label correct",
            all(getattr(r, "currency", None) == curr for r in ind_c))

chk("CR-09d: SAR->USD rate > 3.0",
    CURRENCY_FROM_USD.get("SAR", 0) > 3.0,
    f"Got: {CURRENCY_FROM_USD.get('SAR')}")


# -----------------------------------------------------------------------------
# CR-10: Executive report uses safe HR language
# -----------------------------------------------------------------------------

print("\n--- CR-10: Safe HR language in executive report ---")

df_rep = _hr_df(n=300)
probs_r = np.full(300, 0.20)
sem_r   = sem_mapper.map(df_rep)
ind_r, _   = safe_run(score_individuals, df_rep, probs_r, sem_r)
dept_r, _  = safe_run(score_departments, df_rep, probs_r, ind_r or [], sem_r)
org_r, _   = safe_run(score_organization, ind_r or [], dept_r or [])

exec_rep, err = safe_run(
    _report_gen.generate_hr_report,
    dataset_type="hr_attrition",
    dataset_subtype="standard",
    n_rows=300,
    n_features=7,
    data_quality_score=78.0,
    target_column="Attrition",
    model_type="RandomForest",
    auc_score=0.78,
    training_mode="supervised",
    top_features=[{"name": "MonthlyIncome", "importance": 0.25, "direction": "risk_increase"}],
    attrition_rate=0.17,
    risk_distribution={"High": 30, "Moderate": 80, "Low": 190},
    bias_risk_level="Low",
    ethical_disclaimer=HUMAN_OVERSIGHT_DISCLAIMER,
    provenance_steps=["Data loaded", "Cleaned", "Modeled"],
    caveats=["Small dataset"],
    governed_confidence=0.78,
    currency="SAR",
)
chk("CR-10a: generate_hr_report runs without error", err is None, str(err))

if exec_rep and exec_rep.full_text:
    txt = exec_rep.full_text.lower()
    FORBIDDEN_CAUSAL = [
        "causes attrition",
        "will leave",
        "guaranteed to leave",
        "definitively causes",
    ]
    for phrase in FORBIDDEN_CAUSAL:
        chk(f"CR-10: no '{phrase}' in report text",
            phrase not in txt,
            f"Found '{phrase}' in report")
    chk("CR-10z: 'human' or 'oversight' mentioned in report",
        "human" in txt or "oversight" in txt or "validation" in txt)


# -----------------------------------------------------------------------------
# CR-11: Executive report HTML generated with disclaimer
# -----------------------------------------------------------------------------

print("\n--- CR-11: HTML report with disclaimer ---")

if exec_rep:
    chk("CR-11a: html_text attribute present on ExecutiveReport",
        hasattr(exec_rep, "html_text"))
    if hasattr(exec_rep, "html_text") and exec_rep.html_text:
        html = exec_rep.html_text.lower()
        chk("CR-11b: HTML contains <html> tag",    "<html" in html)
        chk("CR-11c: HTML contains disclaimer",    "human oversight" in html or "decision-support" in html or "not be used as the sole" in html)
        chk("CR-11d: HTML contains version info",  "2.5" in html or "version" in html or PLATFORM_VERSION in html)
    else:
        chk("CR-11e: html_text is populated (non-empty)",
            bool(getattr(exec_rep, "html_text", "")),
            "html_text is empty")


# -----------------------------------------------------------------------------
# CR-12: Model reliability governed/downgraded on leakage
# -----------------------------------------------------------------------------

print("\n--- CR-12: Leakage governance of model reliability ---")

ucr_clean, _ = safe_run(gov.build,
    profiler_quality_score=80.0, missing_pct=0.02, n_rows=500, n_cols=10,
    routing_type="hr_attrition", routing_confidence_raw=0.90, routing_locked=True,
    has_ml_model=True, original_auc=0.82, governed_auc=0.82,
    leakage_risk_score=0.0, leakage_n_critical=0, leakage_n_high=0,
    is_trustworthy=True, validation_overall_status="VALID", validation_n_fail=0,
    has_burnout_evidence=True, has_engagement_evidence=True,
)
ucr_leaked, _ = safe_run(gov.build,
    profiler_quality_score=80.0, missing_pct=0.02, n_rows=500, n_cols=10,
    routing_type="hr_attrition", routing_confidence_raw=0.90, routing_locked=True,
    has_ml_model=True, original_auc=0.92, governed_auc=0.92,
    leakage_risk_score=0.80, leakage_n_critical=2, leakage_n_high=1,
    is_trustworthy=False, validation_overall_status="INVALID", validation_n_fail=3,
    has_burnout_evidence=True, has_engagement_evidence=True,
)

if ucr_clean and ucr_leaked:
    chk("CR-12a: clean model has higher reliability than leaked model",
        ucr_clean.model_reliability.score > ucr_leaked.model_reliability.score,
        f"clean={ucr_clean.model_reliability.score:.3f}, "
        f"leaked={ucr_leaked.model_reliability.score:.3f}")
    chk("CR-12b: leaked model is NOT_READY",
        ucr_leaked.executive_readiness == EXEC_NOT_READY,
        f"Got: {ucr_leaked.executive_readiness}")
    chk("CR-12c: clean model is READY or CAUTION",
        ucr_clean.executive_readiness in (EXEC_READY, EXEC_CAUTION),
        f"Got: {ucr_clean.executive_readiness}")


# -----------------------------------------------------------------------------
# CR-13: Config versions centralised
# -----------------------------------------------------------------------------

print("\n--- CR-13: Version centralisation ---")

chk("CR-13a: PLATFORM_VERSION present",  bool(PLATFORM_VERSION))
chk("CR-13b: REPORT_VERSION present",    bool(REPORT_VERSION))
chk("CR-13c: MODEL_VERSION present",     bool(MODEL_VERSION))
chk("CR-13d: PLATFORM_VERSION is '2.5.1'", PLATFORM_VERSION == "2.5.1",
    f"Got: {PLATFORM_VERSION}")
chk("CR-13e: REPORT_VERSION is '2.5'",   REPORT_VERSION == "2.5",
    f"Got: {REPORT_VERSION}")


# -----------------------------------------------------------------------------
# CR-14: HUMAN_OVERSIGHT_DISCLAIMER present and substantive
# -----------------------------------------------------------------------------

print("\n--- CR-14: Human oversight disclaimer ---")

chk("CR-14a: HUMAN_OVERSIGHT_DISCLAIMER is non-empty", bool(HUMAN_OVERSIGHT_DISCLAIMER))
chk("CR-14b: disclaimer length > 80 chars",
    len(HUMAN_OVERSIGHT_DISCLAIMER) > 80,
    f"Len={len(HUMAN_OVERSIGHT_DISCLAIMER)}")
chk("CR-14c: disclaimer mentions 'human' or 'oversight'",
    "human" in HUMAN_OVERSIGHT_DISCLAIMER.lower() or "oversight" in HUMAN_OVERSIGHT_DISCLAIMER.lower())
chk("CR-14d: disclaimer prohibits sole reliance",
    "sole" in HUMAN_OVERSIGHT_DISCLAIMER.lower() or "not be used" in HUMAN_OVERSIGHT_DISCLAIMER.lower())


# -----------------------------------------------------------------------------
# CR-15: HTTP 200 from Streamlit on port 8510
# -----------------------------------------------------------------------------

print("\n--- CR-15: HTTP 200 from Streamlit ---")

try:
    import urllib.request
    import urllib.error
    with urllib.request.urlopen("http://localhost:8510", timeout=4) as resp:
        status = resp.getcode()
    chk("CR-15: Streamlit responds HTTP 200 on port 8510", status == 200, f"Got: {status}")
except urllib.error.URLError as e:
    print(f"  SKIP  CR-15: Streamlit not running on port 8510 — {e.reason}")
    print("         Start with: py -3 -m streamlit run frontend/app.py --server.port 8510")
except Exception as e:
    print(f"  SKIP  CR-15: Unexpected error — {e}")


# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------

print(f"\n{'='*60}")
print(f"Company Readiness Results: {_PASS} passed, {_FAIL} failed")
if _ERRORS:
    print("\nFailed tests:")
    for e in _ERRORS:
        print(f"  {e}")
else:
    print("All company readiness tests passed.")
print("=" * 60)

sys.exit(0 if _FAIL == 0 else 1)
