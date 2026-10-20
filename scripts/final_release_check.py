"""
Final release check for Adaptive Workforce AI v1.0.0-enterprise-local.

Verifies:
  1. All core backend modules import cleanly
  2. SQLite database initialises correctly
  3. Risk scoring engine runs with minimal synthetic data
  4. Workforce simulation engine runs and returns expected structure
  5. Executive decision intelligence engine runs and returns expected structure
  6. No causal certainty language in key output strings
  7. Governance disclaimers enforced (available=False with zero records)

Run: py scripts/final_release_check.py
"""

import sys
import os
import traceback

# Ensure project root is on the path when running as a script
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

PASS = 0
FAIL = 0
_results: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    global PASS, FAIL
    try:
        fn()
        _results.append((name, True, ""))
        PASS += 1
    except Exception as exc:
        _results.append((name, False, str(exc)))
        FAIL += 1


# ── 1. Module imports ─────────────────────────────────────────────────────────

def _import_modules():
    import backend.core.employee_risk_scoring            # noqa: F401
    import backend.core.ml_validation_engine             # noqa: F401
    import backend.core.workforce_simulation_engine      # noqa: F401
    import backend.core.executive_decision_intelligence  # noqa: F401
    import backend.core.export_safety                    # noqa: F401

check("Core modules import cleanly", _import_modules)


# ── 2. SQLite initialisation ──────────────────────────────────────────────────

def _sqlite_init():
    import sqlite3, tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                dataset_name TEXT,
                result_json TEXT
            )
        """)
        conn.commit()
        conn.close()
    finally:
        os.unlink(db_path)

check("SQLite initialises with WAL mode", _sqlite_init)


# ── 3. Risk scoring with minimal synthetic data ───────────────────────────────

def _risk_scoring():
    from backend.core.employee_risk_scoring import EmployeeRiskScorer
    import pandas as pd
    df = pd.DataFrame({
        "employee_id": [1, 2, 3],
        "department": ["HR", "Ops", "IT"],
        "job_satisfaction": [3, 2, 4],
        "work_life_balance": [3, 2, 4],
        "training_access": [1, 0, 1],
        "internal_opportunities": [1, 0, 1],
        "manager_quality": [3, 2, 4],
        "team_cohesion": [3, 2, 3],
        "recognition": [1, 0, 1],
        "autonomy": [3, 2, 4],
        "workload_stress": [2, 4, 1],
        "role_clarity": [1, 0, 1],
    })
    result = EmployeeRiskScorer().score_dataframe(df)
    assert result is not None, "score_dataframe returned None"
    assert result.total_employee_records >= 1, "No employee records scored"

check("Risk scoring engine runs on synthetic data", _risk_scoring)


# ── 4. Workforce simulation ───────────────────────────────────────────────────

def _simulation():
    from backend.core.workforce_simulation_engine import run_workforce_simulation
    risk_bands = {"Stable": 60, "Monitoring": 20, "Strategic Concern": 12, "Priority Review": 8}
    dept_summary = [{
        "group_label": "department", "group_value": "Operations",
        "total_records": 40, "average_risk_score": 58.0, "average_stability_score": 42.0,
        "stable_count": 20, "monitoring_count": 12,
        "strategic_concern_count": 6, "priority_review_count": 2,
        "top_risk_drivers": ["low_internal_opportunities"],
        "top_protective_drivers": ["high_commitment"],
        "governance_notes": [], "department_recommendations": [],
    }]
    org_drivers = {
        "top_org_risk_drivers": [{
            "driver_name": "Low Internal Opportunities", "source_column": "internal_opp",
            "observed_value": "low", "contribution_direction": "increases_risk",
            "contribution_strength": 72, "explanation_en": "Limited mobility.",
            "explanation_ar": "محدودية التنقل.", "theory_link": "COR",
            "theory_full_en": "Conservation of Resources",
            "theory_full_ar": "نظرية الحفاظ على الموارد", "employee_count": 55,
        }],
        "top_org_protective_factors": [],
    }
    result = run_workforce_simulation(
        total_employee_records=100,
        avg_risk_score=48.0, avg_stability_score=52.0,
        risk_band_counts=risk_bands,
        department_summary=dept_summary,
        org_risk_driver_summary=org_drivers,
        ml_validation=None,
    )
    assert result["available"] is True, f"Simulation unavailable: {result.get('reason')}"
    assert "scenarios" in result and len(result["scenarios"]) >= 1
    assert "baseline" in result

check("Workforce simulation engine runs and returns scenarios", _simulation)


# ── 5. Executive decision intelligence ───────────────────────────────────────

def _decision_intelligence():
    from backend.core.executive_decision_intelligence import run_executive_decision_intelligence
    risk_bands = {"Stable": 60, "Monitoring": 20, "Strategic Concern": 12, "Priority Review": 8}
    result = run_executive_decision_intelligence(
        total_employee_records=100,
        avg_risk_score=48.0, avg_stability_score=52.0,
        risk_band_counts=risk_bands,
        department_summary=[],
        org_risk_driver_summary=None,
        ml_validation=None,
        simulation_result=None,
        workforce_forecast=None,
        governance_warnings=[],
    )
    assert isinstance(result, dict), "Expected dict return"
    assert "available" in result
    assert "computed_at" in result

check("Decision intelligence engine runs and returns dict", _decision_intelligence)


# ── 6. No causal certainty language in DI output ──────────────────────────────

FORBIDDEN_PHRASES = [
    "will definitely", "guaranteed to", "proven cause",
    "definitively causes", "certainly will", "100% certain",
]

def _no_causal_language():
    from backend.core.executive_decision_intelligence import run_executive_decision_intelligence
    risk_bands = {"Stable": 60, "Monitoring": 20, "Strategic Concern": 10, "Priority Review": 8}
    ml_val = {
        "available": True, "reason": None, "target_column": "attrition",
        "n_samples": 100, "n_train": 75, "n_test": 25,
        "n_positive": 20, "n_negative": 80,
        "best_model": "RandomForest", "model_results": [],
        "selected_metrics": {
            "roc_auc": 0.76, "mcc": 0.44, "f1_score": 0.63,
            "precision": 0.67, "recall": 0.60, "accuracy": 0.85,
            "brier_score": 0.13, "calibration_error": 0.05, "optimal_threshold": 0.38,
        },
        "feature_importance": [{"feature": "internal_opportunities", "importance": 0.18, "rank": 1}],
        "confusion_matrix": {"tp": 14, "tn": 72, "fp": 8, "fn": 6},
        "governance": {
            "pii_columns_removed": [], "leakage_columns_removed": [],
            "identifier_columns_removed": [], "excluded_columns": [],
            "ml_governance_warnings": [], "feature_count": 15,
        },
        "conservative": None, "computed_at": "2026-05-23T10:00:00",
    }
    result = run_executive_decision_intelligence(
        total_employee_records=100,
        avg_risk_score=48.0, avg_stability_score=52.0,
        risk_band_counts=risk_bands,
        department_summary=[], org_risk_driver_summary=None,
        ml_validation=ml_val, simulation_result=None,
        workforce_forecast=None, governance_warnings=[],
    )
    texts_to_check = [
        result.get("board_summary_en", ""),
        result.get("board_summary_ar", ""),
        result.get("limitations", [""])[0] if result.get("limitations") else "",
    ]
    for priority in result.get("strategic_priorities", []):
        texts_to_check.extend([
            priority.get("priority_en", ""),
            priority.get("recommended_next_step_en", ""),
            priority.get("confidence_reason_en", ""),
        ])
    for q in result.get("top_decision_questions", []):
        texts_to_check.extend([q.get("answer_en", ""), q.get("governance_note", "")])
    for text in texts_to_check:
        for phrase in FORBIDDEN_PHRASES:
            assert phrase.lower() not in text.lower(), \
                f"Causal phrase '{phrase}' found in: {text[:80]}"

check("No causal certainty language in decision intelligence output", _no_causal_language)


# ── 7. Governance enforced — zero records → unavailable ───────────────────────

def _governance_zero_records():
    from backend.core.executive_decision_intelligence import run_executive_decision_intelligence
    result = run_executive_decision_intelligence(
        total_employee_records=0,
        avg_risk_score=0.0, avg_stability_score=0.0,
        risk_band_counts={}, department_summary=[],
        org_risk_driver_summary=None, ml_validation=None,
        simulation_result=None, workforce_forecast=None,
        governance_warnings=[],
    )
    assert result["available"] is False, "Expected available=False for zero records"
    assert result.get("reason"), "Expected non-empty reason when unavailable"

check("Governance: zero records -> available=False with reason", _governance_zero_records)


# ── Results ──────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("  Adaptive Workforce AI — Final Release Check")
print("  v1.0.0-enterprise-local | 2026-05-23")
print("=" * 60)
for name, passed, error in _results:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}")
    if error:
        print(f"         -> {error[:120]}")
print()
print(f"  Results: {PASS} passed, {FAIL} failed out of {PASS + FAIL} checks")
print("=" * 60)
print()

if FAIL > 0:
    sys.exit(1)
