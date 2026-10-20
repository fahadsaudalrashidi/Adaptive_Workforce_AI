"""
Routing validation tests — Phase 2
Run: py -3 test_routing.py
"""
import sys
import types
import warnings
warnings.filterwarnings("ignore")

# Stub ONLY modules that are truly absent (won't shadow real installed packages)
_ABSENT_STUBS = [
    "streamlit",
    "rapidfuzz", "rapidfuzz.process", "rapidfuzz.fuzz",
    "sklearn", "sklearn.preprocessing", "sklearn.ensemble",
    "sklearn.linear_model", "sklearn.metrics",
    "sklearn.model_selection", "sklearn.pipeline",
    "sklearn.impute", "sklearn.decomposition",
    "imblearn", "imblearn.pipeline", "imblearn.over_sampling",
    "xgboost", "lightgbm", "catboost", "optuna",
    "plotly", "plotly.express", "plotly.graph_objects",
    "statsmodels", "statsmodels.tsa", "statsmodels.tsa.holtwinters",
    "prophet", "shap", "matplotlib", "matplotlib.pyplot",
    "openpyxl", "xlrd", "fastparquet",
]

import importlib
for mod in _ABSENT_STUBS:
    if mod in sys.modules:
        continue
    try:
        importlib.import_module(mod)
    except (ImportError, ModuleNotFoundError):
        sys.modules[mod] = types.ModuleType(mod)

import pandas as pd
import numpy as np
sys.path.insert(0, ".")

from backend.core.dataset_contract import DatasetContract, build_contract
from backend.core.adaptive_router import AdaptiveRouter

router = AdaptiveRouter()
PASS = 0
FAIL = 0
rng = np.random.default_rng(42)


def chk(name, cond, got=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}  [got: {got}]")
        FAIL += 1


# ══════════════════════════════════════════════════════════════════
# TEST A — Saudi HR Attrition
# ══════════════════════════════════════════════════════════════════
print("\nTEST A — Saudi HR Attrition dataset")
df_hr = pd.DataFrame({
    "EmployeeID":      range(200),
    "Age":             rng.integers(22, 60, 200),
    "Department":      ["Engineering"] * 100 + ["Sales"] * 100,
    "JobRole":         ["Engineer"] * 200,
    "MonthlyIncome":   rng.integers(5000, 25000, 200),
    "YearsAtCompany":  rng.integers(0, 20, 200),
    "Attrition":       rng.choice(["Yes", "No"], 200),
    "Gender":          rng.choice(["Male", "Female"], 200),
    "JobSatisfaction": rng.integers(1, 5, 200),
    "OverTime":        rng.choice(["Yes", "No"], 200),
    "EducationField":  ["Science"] * 200,
    "MaritalStatus":   rng.choice(["Single", "Married"], 200),
})
c = router.route(df_hr, filename="employee_attrition.xlsx")
chk("A1 type=hr_attrition",     c.dataset_type == "hr_attrition",         c.dataset_type)
chk("A2 row_unit=employees",    c.row_unit == "employees",                  c.row_unit)
chk("A3 is_hr=True",            c.is_hr)
chk("A4 is_biosignal=False",    not c.is_biosignal)
chk("A5 attrition allowed",     c.allows("attrition_prediction"),           c.blocked_analyses)
chk("A6 target_available=True", c.target_available)
chk("A7 row_label has employee","employee" in c.row_label(),               c.row_label())

# ══════════════════════════════════════════════════════════════════
# TEST B — WESAD HR.csv
# ══════════════════════════════════════════════════════════════════
print("\nTEST B — WESAD HR.csv (heart-rate biosignal)")
df_hr_bio = pd.DataFrame({"HR": rng.uniform(55, 110, 2000).astype(float)})
c = router.route(df_hr_bio, filename="HR.csv")
chk("B1 type=biosignal",          c.dataset_type == "biosignal_timeseries", c.dataset_type)
chk("B2 row_unit=signal_samples", c.row_unit == "signal_samples",           c.row_unit)
chk("B3 is_biosignal=True",       c.is_biosignal)
chk("B4 attrition BLOCKED",       c.blocks("attrition_prediction"))
chk("B5 burnout BLOCKED",         c.blocks("burnout_intelligence"))
chk("B6 dept_stability BLOCKED",  c.blocks("department_stability"))
chk("B7 row_label=signal sample", "sample" in c.row_label(plural=False),   c.row_label(False))
chk("B8 no employee_columns",     len(c.employee_columns) == 0)
chk("B9 biosignal warning",       any("BIOSIGNAL" in w for w in c.warning_messages))

# ══════════════════════════════════════════════════════════════════
# TEST C — WESAD BVP.csv
# ══════════════════════════════════════════════════════════════════
print("\nTEST C — WESAD BVP.csv (blood volume pulse)")
df_bvp = pd.DataFrame({"BVP": rng.uniform(-200, 200, 5039).astype(float)})
c = router.route(df_bvp, filename="BVP.csv")
chk("C1 type=biosignal",          c.dataset_type == "biosignal_timeseries", c.dataset_type)
chk("C2 row_unit=signal_samples", c.row_unit == "signal_samples",           c.row_unit)
chk("C3 is_biosignal=True",       c.is_biosignal)
chk("C4 attrition BLOCKED",       c.blocks("attrition_prediction"))
chk("C5 retention_roi BLOCKED",   c.blocks("retention_roi"))
chk("C6 fairness_audit BLOCKED",  c.blocks("fairness_audit"))
chk("C7 pdf_report BLOCKED",      c.blocks("pdf_report"))
chk("C8 signal_type=BVP",         c.detected_signal_type == "BVP",          c.detected_signal_type)
chk("C9 row_label=signal samples","sample" in c.row_label(),               c.row_label())

# ══════════════════════════════════════════════════════════════════
# TEST D — WESAD EDA.csv
# ══════════════════════════════════════════════════════════════════
print("\nTEST D — WESAD EDA.csv (electrodermal activity)")
df_eda = pd.DataFrame({"EDA": rng.uniform(0, 20, 5039).astype(float)})
c = router.route(df_eda, filename="EDA.csv")
chk("D1 type=biosignal",          c.dataset_type == "biosignal_timeseries", c.dataset_type)
chk("D2 row_unit=signal_samples", c.row_unit == "signal_samples",           c.row_unit)
chk("D3 is_biosignal=True",       c.is_biosignal)
chk("D4 attrition BLOCKED",       c.blocks("attrition_prediction"))
chk("D5 pdf_report BLOCKED",      c.blocks("pdf_report"))
chk("D6 biosignal_stress allowed",c.allows("biosignal_stress_analysis"),   c.compatible_analyses)
chk("D7 signal_type=EDA",         c.detected_signal_type == "EDA",         c.detected_signal_type)

# ══════════════════════════════════════════════════════════════════
# TEST E — Unknown CSV
# ══════════════════════════════════════════════════════════════════
print("\nTEST E — Unknown CSV (random columns)")
df_unk = pd.DataFrame({
    "col_a": rng.random(50),
    "col_b": rng.random(50),
    "col_c": rng.random(50),
})
c = router.route(df_unk, filename="random_data.csv")
chk("E1 type in unknown set",  c.dataset_type in ("unknown", "generic_timeseries", "productivity_logs"), c.dataset_type)
chk("E2 attrition BLOCKED",   c.blocks("attrition_prediction"))
chk("E3 data_profiling ok",   c.allows("data_profiling"))
chk("E4 not biosignal",       not c.is_biosignal)

# ══════════════════════════════════════════════════════════════════
# TEST F — Partial HR (no Attrition column)
# ══════════════════════════════════════════════════════════════════
print("\nTEST F — Partial HR (no Attrition column)")
df_partial = pd.DataFrame({
    "EmployeeID":       range(80),
    "Age":              rng.integers(25, 55, 80),
    "Department":       ["IT"] * 40 + ["HR"] * 40,
    "MonthlyIncome":    rng.integers(6000, 20000, 80),
    "YearsAtCompany":   rng.integers(1, 15, 80),
    "Gender":           rng.choice(["Male", "Female"], 80),
    "JobSatisfaction":  rng.integers(1, 5, 80),
    "PerformanceRating":rng.integers(1, 5, 80),
})
c = router.route(df_partial, filename="workforce_partial.csv")
chk("F1 is hr type",          c.is_hr or "hr" in c.dataset_type,           c.dataset_type)
chk("F2 attrition BLOCKED",   c.blocks("attrition_prediction"))
chk("F3 target_available=F",  not c.target_available)
chk("F4 data_profiling ok",   c.allows("data_profiling"))
chk("F5 not biosignal",       not c.is_biosignal)

print()
print("=" * 50)
print(f"TOTAL: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
