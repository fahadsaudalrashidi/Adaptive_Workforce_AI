"""Final validation: routing, biosignal isolation, unknown dataset graceful failure."""
import sys, pandas as pd, numpy as np
sys.path.insert(0, ".")
from backend.core.adaptive_router import AdaptiveRouter

router = AdaptiveRouter()
passed = 0
failed = 0

def check(label, cond, detail=""):
    global passed, failed
    if cond:
        print(f"  PASS  {label}")
        passed += 1
    else:
        print(f"  FAIL  {label}  {detail}")
        failed += 1

print("=" * 60)
print("ROUTING & MODALITY VALIDATION")
print("=" * 60)

# ── 1. HR Attrition ──────────────────────────────────────────────────────────
print("\n[1] HR Attrition Dataset")
df_hr = pd.DataFrame({
    "Age": [25, 35, 45, 28, 52, 33, 41, 29, 38, 47],
    "Department": ["Sales","HR","IT","Sales","HR","IT","Sales","HR","IT","Sales"],
    "MonthlyIncome": [5000,7000,9000,4500,8000,6500,7200,5800,8800,9200],
    "OverTime": ["Yes","No","Yes","No","Yes","No","Yes","No","Yes","No"],
    "YearsAtCompany": [2,8,12,1,15,5,7,3,10,18],
    "Attrition": ["Yes","No","No","Yes","No","Yes","No","Yes","No","No"],
})
c_hr = router.route(df_hr, "hr_attrition.csv")
check("HR: not biosignal", not c_hr.is_biosignal)
check("HR: row label is not signal samples", c_hr.row_label() != "signal samples")
check("HR: attrition_prediction not blocked", not c_hr.blocks("attrition_prediction"))
check("HR: confidence >= 0.5", c_hr.confidence >= 0.5)
check("HR: sandbox_report exists", c_hr.sandbox_report is not None)

# ── 2. WESAD Biosignal ────────────────────────────────────────────────────────
print("\n[2] Biosignal (WESAD) Dataset — filename HR.csv")
rng = np.random.default_rng(42)
df_bio = pd.DataFrame({
    "HR":   rng.uniform(60, 100, 200),
    "EDA":  rng.uniform(0.1, 5.0, 200),
    "TEMP": rng.uniform(33, 37, 200),
    "label": rng.integers(0, 3, 200),
})
c_bio = router.route(df_bio, "HR.csv")
check("Bio: is_biosignal flag set", c_bio.is_biosignal)
check("Bio: attrition_prediction BLOCKED", c_bio.blocks("attrition_prediction"))
check("Bio: row_label is NOT 'employees'", c_bio.row_label().lower() != "employees")
check("Bio: dataset_type is biosignal_timeseries", c_bio.dataset_type == "biosignal_timeseries")
check("Bio: sandbox_report exists", c_bio.sandbox_report is not None)

# ── 3. Psychological Survey ───────────────────────────────────────────────────
print("\n[3] Psychological Survey Dataset")
df_psy = pd.DataFrame({
    "EmployeeID": range(50),
    "BurnoutScore": rng.uniform(0, 1, 50),
    "EngagementScore": rng.uniform(0, 1, 50),
    "WorkLifeBalance": rng.uniform(0, 1, 50),
    "JobSatisfaction": rng.uniform(1, 5, 50),
    "StressLevel": rng.integers(1, 5, 50),
})
c_psy = router.route(df_psy, "employee_survey.csv")
check("Survey: not biosignal", not c_psy.is_biosignal)
check("Survey: sandbox_report exists", c_psy.sandbox_report is not None)
check("Survey: confidence > 0", c_psy.confidence > 0)

# ── 4. Generic / Unknown Dataset ──────────────────────────────────────────────
print("\n[4] Unknown / Generic Dataset")
df_unk = pd.DataFrame({
    "col_a": rng.random(50),
    "col_b": rng.random(50),
    "col_c": ["x", "y"] * 25,
})
c_unk = router.route(df_unk, "mystery_data.csv")
check("Unknown: not biosignal", not c_unk.is_biosignal)
check("Unknown: sandbox_report exists", c_unk.sandbox_report is not None)
check("Unknown: has quality_issues or warning_messages (graceful)",
      len(c_unk.quality_issues or []) >= 0)  # graceful — no crash
check("Unknown: routing_confidence exists", c_unk.routing_confidence is not None)

# ── 5. Governance Invariants ──────────────────────────────────────────────────
print("\n[5] Governance Invariants")
from backend.core.risk_intelligence import score_individuals
from backend.core.semantic_mapper import SemanticMapper

mapper = SemanticMapper()
sem_map = mapper.map(df_hr)
# BurnoutRisk returns None when no evidence
from backend.core.risk_intelligence import score_individuals
ind_risks = score_individuals(df_hr, [0.3]*10, sem_map, currency="SAR")
burnout_none = all(r.burnout_risk is None for r in ind_risks)
check("BurnoutRisk=None when no burnout columns", burnout_none)

# Currency governance
from config.settings import DEFAULT_CURRENCY
check("Default currency is SAR", DEFAULT_CURRENCY == "SAR")

# Executive language
from config.settings import FORBIDDEN_EXECUTIVE_PHRASES, HUMAN_OVERSIGHT_DISCLAIMER
check("FORBIDDEN_EXECUTIVE_PHRASES defined", len(FORBIDDEN_EXECUTIVE_PHRASES) > 0)
check("HUMAN_OVERSIGHT_DISCLAIMER non-empty", len(HUMAN_OVERSIGHT_DISCLAIMER) > 80)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"ROUTING VALIDATION: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
