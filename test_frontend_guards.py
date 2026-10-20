"""
Frontend guard-clause validation test.
Tests that safe_render_* utilities correctly block/allow based on DatasetContract.
Run: py -3 test_frontend_guards.py
"""
import sys
import types
import importlib
import warnings
warnings.filterwarnings("ignore")

# ── Stub absent dependencies ────────────────────────────────────────────────
_ABSENT_STUBS = [
    "streamlit",
    "rapidfuzz", "rapidfuzz.process", "rapidfuzz.fuzz",
    "statsmodels", "statsmodels.tsa", "statsmodels.tsa.holtwinters",
    "prophet", "shap",
]
for mod in _ABSENT_STUBS:
    if mod in sys.modules:
        continue
    try:
        importlib.import_module(mod)
    except (ImportError, ModuleNotFoundError):
        sys.modules[mod] = types.ModuleType(mod)

# Streamlit needs attribute stubs for set_page_config etc.
st_mock = sys.modules["streamlit"]
st_mock.session_state = {}
st_mock.set_page_config = lambda **kw: None
st_mock.cache_resource  = lambda fn: fn
st_mock.cache_data      = lambda fn: fn

import pandas as pd
import numpy as np
sys.path.insert(0, ".")

from backend.core.adaptive_router import AdaptiveRouter
from backend.core.dataset_contract import build_contract

router = AdaptiveRouter()
PASS = 0; FAIL = 0
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
# Test safe_render_* routing logic (contract-level, without Streamlit)
# ══════════════════════════════════════════════════════════════════

print("\nGUARD-A: Biosignal contract blocks all employee analytics")
df_bvp = pd.DataFrame({"BVP": rng.uniform(-200, 200, 5039).astype(float)})
c_bio = router.route(df_bvp, filename="BVP.csv")

chk("GA1 is_biosignal=True",             c_bio.is_biosignal)
chk("GA2 row_unit=signal_samples",        c_bio.row_unit == "signal_samples", c_bio.row_unit)
chk("GA3 blocks attrition_prediction",    c_bio.blocks("attrition_prediction"))
chk("GA4 blocks burnout_intelligence",    c_bio.blocks("burnout_intelligence"))
chk("GA5 blocks department_stability",    c_bio.blocks("department_stability"))
chk("GA6 blocks retention_roi",           c_bio.blocks("retention_roi"))
chk("GA7 blocks fairness_audit",          c_bio.blocks("fairness_audit"))
chk("GA8 blocks pdf_report",              c_bio.blocks("pdf_report"))
chk("GA9 allows biosignal_stress",        c_bio.allows("biosignal_stress_analysis"))
chk("GA10 allows data_profiling",         c_bio.allows("data_profiling"))
chk("GA11 row_label never employees",     "employee" not in c_bio.row_label().lower(), c_bio.row_label())

print("\nGUARD-B: HR contract allows employee analytics")
df_hr = pd.DataFrame({
    "EmployeeID":      range(200),
    "Age":             rng.integers(22, 60, 200),
    "Department":      rng.choice(["Eng", "Sales", "HR"], 200),
    "MonthlyIncome":   rng.integers(5000, 25000, 200),
    "YearsAtCompany":  rng.integers(0, 20, 200),
    "Attrition":       rng.choice(["Yes", "No"], 200),
    "Gender":          rng.choice(["Male", "Female"], 200),
    "JobSatisfaction": rng.integers(1, 5, 200),
})
c_hr = router.route(df_hr, filename="employee_attrition.xlsx")

chk("GB1 is_hr=True",                     c_hr.is_hr)
chk("GB2 row_unit=employees",             c_hr.row_unit == "employees", c_hr.row_unit)
chk("GB3 allows attrition_prediction",    c_hr.allows("attrition_prediction"))
chk("GB4 not blocks attrition",           not c_hr.blocks("attrition_prediction"))
chk("GB5 row_label=employees",            "employee" in c_hr.row_label().lower(), c_hr.row_label())
chk("GB6 is_biosignal=False",             not c_hr.is_biosignal)
chk("GB7 target_available=True",          c_hr.target_available)
chk("GB8 no BIOSIGNAL warning in HR",    not any("BIOSIGNAL" in w for w in c_hr.warning_messages), c_hr.warning_messages)

print("\nGUARD-C: Unknown contract blocks predictions but allows profiling")
df_unk = pd.DataFrame({"x": rng.random(50), "y": rng.random(50)})
c_unk = router.route(df_unk, filename="mystery.csv")

chk("GC1 attrition blocked",             c_unk.blocks("attrition_prediction"))
chk("GC2 biosignal_stress blocked",      c_unk.blocks("biosignal_stress_analysis"))
chk("GC3 data_profiling allowed",        c_unk.allows("data_profiling"))
chk("GC4 not biosignal",                 not c_unk.is_biosignal)

print("\nGUARD-D: PDF routing logic")
# Biosignal → biosignal PDF (blocks pdf_report but biosignal export allowed)
chk("GD1 biosignal blocks pdf_report",   c_bio.blocks("pdf_report"))
# HR → HR PDF allowed (pdf_report is in compatible list)
chk("GD2 hr allows pdf_report",          c_hr.allows("pdf_report"), str(c_hr.blocked_analyses))

print("\nGUARD-E: Compatibility matrix completeness")
for c, name in [(c_bio, "biosignal"), (c_hr, "hr"), (c_unk, "unknown")]:
    matrix_keys = {e.analysis_key for e in c.compatibility_matrix}
    from backend.core.dataset_contract import ANALYSIS_KEYS
    chk(f"GE-{name} matrix covers all keys", matrix_keys == set(ANALYSIS_KEYS),
        f"missing: {set(ANALYSIS_KEYS) - matrix_keys}")
    # Every key must be in exactly one of compatible/blocked
    for key in ANALYSIS_KEYS:
        in_compat  = key in c.compatible_analyses
        in_blocked = key in c.blocked_analyses
        chk(f"GE-{name}-{key} in exactly one list",
            in_compat != in_blocked,
            f"both={in_compat and in_blocked}, neither={not in_compat and not in_blocked}")

print("\nGUARD-F: row_label() returns correct labels for all row_unit types")
from backend.core.dataset_contract import DatasetContract, build_contract, ANALYSIS_KEYS as _AK

# Test row_label() directly by setting row_unit on a minimal contract instance
label_cases = [
    ("employees",        "employee",       "employees"),
    ("signal_samples",   "signal sample",  "signal samples"),
    ("survey_responses", "survey response","survey responses"),
    ("time_windows",     "time window",    "time windows"),
    ("events",           "event",          "events"),
    ("records",          "record",         "records"),
    ("unknown",          "record",         "records"),
]
# Build a base contract and mutate row_unit directly for testing row_label()
base = build_contract(
    dataset_type="unknown", dataset_subtype="test",
    confidence=0.9, target_available=False, target_column=None,
    subject_id_column=None, time_column=None,
    signal_columns=[], employee_columns=[],
    recommended_pipeline="test", reason="test",
)
for (row_unit, sing_expect, plur_expect) in label_cases:
    base.row_unit = row_unit  # mutate for testing
    chk(f"GF row_label singular [{row_unit}]",
        base.row_label(plural=False) == sing_expect,
        f"expected '{sing_expect}' got '{base.row_label(plural=False)}'")
    chk(f"GF row_label plural [{row_unit}]",
        base.row_label(plural=True) == plur_expect,
        f"expected '{plur_expect}' got '{base.row_label(plural=True)}'")

print()
print("=" * 60)
print(f"TOTAL: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
