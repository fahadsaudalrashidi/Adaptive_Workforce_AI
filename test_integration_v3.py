"""
Integration test for new universal architecture modules.
Run: py -3 test_integration_v3.py
"""
import sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
import numpy as np
import pandas as pd

from backend.core.adaptive_router import AdaptiveRouter

router = AdaptiveRouter()
rng = np.random.default_rng(42)
PASS = 0; FAIL = 0

def chk(name, cond, got=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}  [got: {got}]")
        FAIL += 1

# ── Test 1: BVP.csv biosignal ────────────────────────────────────────────────
print("\nT1: BVP.csv — must route to biosignal with all Phase 3 results")
df_bio = pd.DataFrame({"BVP": rng.uniform(-200, 200, 5039).astype(float)})
c = router.route(df_bio, "BVP.csv")

chk("T1a is_biosignal=True",          c.is_biosignal)
chk("T1b row_unit=signal_samples",    c.row_unit == "signal_samples", c.row_unit)
chk("T1c modality_result populated",  c.modality_result is not None)
chk("T1d routing_confidence populated", c.routing_confidence is not None)
chk("T1e semantic_map_v2 populated",  c.semantic_map_v2 is not None)
chk("T1f sandbox_report populated",   c.sandbox_report is not None)
chk("T1g modality=BIOSIGNAL",         c.modality_result.modality.value == "biosignal_timeseries" if c.modality_result else False,
    c.modality_result.modality.value if c.modality_result else "N/A")
chk("T1h routing locked (hard rule)", c.routing_confidence.routing_locked if c.routing_confidence else False)
chk("T1i routing confidence >= 0.90", (c.routing_confidence.overall_confidence >= 0.90) if c.routing_confidence else False,
    str(c.routing_confidence.overall_confidence) if c.routing_confidence else "N/A")
chk("T1j attrition blocked in sandbox", "attrition_prediction" in (c.sandbox_report.globally_blocked if c.sandbox_report else []))
chk("T1k data_profiling available",   "data_profiling" in (c.sandbox_report.globally_available if c.sandbox_report else []))
chk("T1l row_label never employees",  "employee" not in c.row_label().lower(), c.row_label())

# ── Test 2: HR dataset ────────────────────────────────────────────────────────
print("\nT2: HR employee dataset — must route to HR with sandbox allowing attrition")
df_hr = pd.DataFrame({
    "EmployeeID": range(200),
    "Age": rng.integers(22, 60, 200),
    "Department": rng.choice(["Eng", "Sales", "HR"], 200),
    "MonthlyIncome": rng.integers(5000, 25000, 200),
    "YearsAtCompany": rng.integers(0, 20, 200),
    "Attrition": rng.choice(["Yes", "No"], 200),
    "Gender": rng.choice(["Male", "Female"], 200),
    "JobSatisfaction": rng.integers(1, 5, 200),
})
c2 = router.route(df_hr, "employee_attrition.xlsx")

chk("T2a is_hr=True",                 c2.is_hr)
chk("T2b target detected",            c2.target_available)
chk("T2c semantic_map_v2 populated",  c2.semantic_map_v2 is not None)
chk("T2d sandbox populated",          c2.sandbox_report is not None)
# HR dataset: attrition should NOT be in global_blocked (it's HR with target)
chk("T2e attrition NOT globally blocked", "attrition_prediction" not in (c2.sandbox_report.globally_blocked if c2.sandbox_report else ["attrition_prediction"]))
# Protected attrs: Gender should be detected by semantic mapper
sem = c2.semantic_map_v2
chk("T2f protected attributes detected", len(sem.protected_attributes) >= 1 if sem else False,
    str(sem.protected_attributes) if sem else "N/A")
chk("T2g target in sem mapper",       bool(sem.target_candidates) if sem else False,
    str(sem.target_candidates) if sem else "N/A")

# ── Test 3: Unknown dataset ───────────────────────────────────────────────────
print("\nT3: Unknown dataset — must degrade gracefully")
df_unk = pd.DataFrame({"x": rng.random(50), "y": rng.random(50)})
c3 = router.route(df_unk, "mystery.csv")

chk("T3a attrition blocked",          c3.blocks("attrition_prediction"))
chk("T3b biosignal blocked",          c3.blocks("biosignal_stress_analysis"))
chk("T3c data_profiling allowed",     c3.allows("data_profiling"))
chk("T3d modality_result populated",  c3.modality_result is not None)
chk("T3e routing_confidence populated", c3.routing_confidence is not None)
chk("T3f not biosignal",              not c3.is_biosignal)

# ── Test 4: EDA.csv biosignal ─────────────────────────────────────────────────
print("\nT4: EDA.csv — filename hard rule + new engines")
df_eda = pd.DataFrame({"EDA": rng.exponential(2.0, 20000)})
c4 = router.route(df_eda, "EDA.csv")

chk("T4a EDA is_biosignal",           c4.is_biosignal)
chk("T4b row_unit=signal_samples",    c4.row_unit == "signal_samples", c4.row_unit)
chk("T4c modality routing_locked",    c4.routing_confidence.routing_locked if c4.routing_confidence else False)

# ── Test 5: Modality classifier standalone ───────────────────────────────────
print("\nT5: ModalityClassifier standalone")
from backend.core.modality_classifier import ModalityClassifier, Modality

mc = ModalityClassifier()
r_bio = mc.classify(df_bio, "BVP.csv")
chk("T5a BVP->BIOSIGNAL",             r_bio.modality == Modality.BIOSIGNAL, r_bio.modality.value)
chk("T5b BVP confidence >= 0.90",    r_bio.confidence >= 0.90, str(r_bio.confidence))
chk("T5c BVP row_unit_hint",         r_bio.row_unit_hint == "signal_samples", r_bio.row_unit_hint)

r_hr = mc.classify(df_hr, "employee_attrition.xlsx")
chk("T5d HR->TABULAR_HR",             r_hr.modality == Modality.TABULAR_HR, r_hr.modality.value)

# ── Test 6: SemanticColumnMapper standalone ──────────────────────────────────
print("\nT6: SemanticColumnMapper standalone")
from backend.core.semantic_column_mapper import SemanticColumnMapper, SemanticRole

mapper = SemanticColumnMapper()
sm = mapper.map(df_hr)
chk("T6a target candidate detected", "Attrition" in sm.target_candidates, str(sm.target_candidates))
chk("T6b protected attr detected",   "Gender" in sm.protected_attributes, str(sm.protected_attributes))
chk("T6c hr columns detected",       len(sm.hr_columns) > 0, str(sm.hr_columns))

sm_bio = mapper.map(df_bio)
chk("T6d biosignal column detected", len(sm_bio.biosignal_columns) > 0, str(sm_bio.biosignal_columns))

# ── Test 7: FailSafeGuardrails standalone ────────────────────────────────────
print("\nT7: FailSafeGuardrails sandbox validation")
from backend.core.fail_safe_guardrails import SandboxValidator
from backend.core.modality_classifier import ModalityClassifier
from backend.core.dataset_confidence_engine import DatasetConfidenceEngine

sv  = SandboxValidator()
mc2 = ModalityClassifier()
ce  = DatasetConfidenceEngine()

mr_bio = mc2.classify(df_bio, "BVP.csv")
rc_bio = ce.score(mr_bio, df_bio, "BVP.csv")
ctx_bio = {"target_available": False, "target_column": None,
           "feature_columns": [], "missing_rate_overall": 0.0,
           "has_department_column": False, "has_temporal_column": False,
           "semantic_mapping": None}
sb_bio = sv.validate_all(mr_bio, rc_bio, df_bio, ctx_bio)

chk("T7a biosignal attrition BLOCKED", "attrition_prediction" in sb_bio.globally_blocked)
chk("T7b biosignal data_profiling OK", "data_profiling" in sb_bio.globally_available)
chk("T7c biosignal health > 0",        sb_bio.dataset_health_score > 0.0)
chk("T7d biosignal modality correct",  sb_bio.modality == "biosignal_timeseries", sb_bio.modality)

mr_hr  = mc2.classify(df_hr, "employee_attrition.xlsx")
rc_hr  = ce.score(mr_hr, df_hr, "employee_attrition.xlsx")
ctx_hr = {"target_available": True, "target_column": "Attrition",
          "feature_columns": [c for c in df_hr.columns if c != "Attrition"],
          "missing_rate_overall": 0.0,
          "has_department_column": True, "has_temporal_column": False,
          "semantic_mapping": None}
sb_hr  = sv.validate_all(mr_hr, rc_hr, df_hr, ctx_hr)
chk("T7e HR attrition guard result present", "attrition_prediction" in sb_hr.validated_analyses)

# ── Test 8: TelemetryEngine ──────────────────────────────────────────────────
print("\nT8: TelemetryEngine")
from backend.core.telemetry_engine import TelemetryEngine

tel = TelemetryEngine(session_id="test-001", persist_to_db=False)
tel.log_upload("BVP.csv", n_rows=5039, n_cols=1)
tel.log_modality("biosignal_timeseries", 0.99, "wesad_bvp", 0.95)
tel.log_confidence("biosignal_timeseries", 0.97, "Very High", ["attrition_prediction"])
tel.log_guard_result("attrition_prediction", False, ["Biosignal data cannot produce attrition"], [])
summary = tel.summarise()

chk("T8a events logged",              summary.n_events >= 4)
chk("T8b upload logged",              summary.n_uploads == 1)
chk("T8c guard block logged",         summary.n_guard_blocks == 1)
chk("T8d session health > 0",         summary.overall_health > 0.0)

# ── Test 9: AdaptiveVisualizationEngine ──────────────────────────────────────
print("\nT9: AdaptiveVisualizationEngine")
from backend.core.adaptive_visualization_engine import AdaptiveVisualizationEngine, ChartType

ave = AdaptiveVisualizationEngine()
mr_hr2 = mc2.classify(df_hr, "hr.csv")
sm_hr  = mapper.map(df_hr)
charts = ave.recommend(df_hr, mr_hr2, sm_hr, contract_keys_allowed=["data_profiling","schema_mapping","attrition_prediction","department_stability","fairness_audit"])

chk("T9a charts generated > 0",       len(charts) > 0, str(len(charts)))
chk("T9b charts have confidence",     all(c.confidence > 0 for c in charts))
chk("T9c charts have rationale",      all(c.rationale for c in charts))
chk("T9d distribution chart present", any(c.chart_type == ChartType.DISTRIBUTION_GRID for c in charts))

bio_charts = ave.recommend(df_bio, mr_bio, sm_bio, contract_keys_allowed=["biosignal_stress_analysis"])
# For biosignal, should not include HR-specific charts that require attrition_prediction
hr_restricted = [c for c in bio_charts if c.requires_contract_key == "attrition_prediction"]
chk("T9e no attrition charts for biosignal", len(hr_restricted) == 0, str([c.chart_id for c in hr_restricted]))

print()
print("=" * 60)
print(f"TOTAL: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
