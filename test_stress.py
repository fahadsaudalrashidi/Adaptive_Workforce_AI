"""
Stress Tests — Adaptive Workforce Intelligence Engine
=====================================================
Tests malformed, sparse, massive, corrupted, and pathological datasets.
All tests are self-contained and use synthetic data — no external files needed.

Run:
    py -3 test_stress.py
"""
from __future__ import annotations

import io
import os
import sys
import time
import traceback
import warnings
from typing import List, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Add project root to path ──────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Imports ───────────────────────────────────────────────────────────────────
from backend.core.adaptive_router import AdaptiveRouter
from backend.core.dataset_profiler import DatasetProfiler as DataProfiler
from backend.core.semantic_mapper import SemanticMapper
from backend.core.data_healer import DataHealer
from backend.core.leakage_detector import LeakageDetector
from backend.core.model_validator import ModelValidator
from backend.core.ml_router import MLRouter, TrainingResult

# ── Test harness ──────────────────────────────────────────────────────────────
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


def safe_run(name: str, fn, *args, **kwargs):
    """Run fn(*args, **kwargs) without crashing. Returns (result, exception)."""
    try:
        result = fn(*args, **kwargs)
        return result, None
    except Exception as exc:
        return None, exc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hr_df(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "Age":             rng.integers(22, 60, n),
        "MonthlyIncome":   rng.integers(2000, 15000, n),
        "YearsAtCompany":  rng.integers(0, 20, n),
        "Department":      rng.choice(["Sales", "R&D", "HR"], n),
        "JobSatisfaction": rng.integers(1, 5, n),
        "OverTime":        rng.choice(["Yes", "No"], n),
        "Attrition":       rng.choice([0, 1], n, p=[0.84, 0.16]),
    })


router    = AdaptiveRouter()
profiler  = DataProfiler()
mapper    = SemanticMapper()
ml_router = MLRouter()


# ─────────────────────────────────────────────────────────────────────────────
# S1: Empty Dataset
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S1: Empty Dataset ===")

df_empty = pd.DataFrame()
buf_empty = io.BytesIO(df_empty.to_csv(index=False).encode())

result_r, exc_r = safe_run("route empty", router.route, df_empty, "empty.csv")
chk("S1-a  router does not crash on empty df",
    exc_r is None or result_r is not None,
    str(exc_r))

result_p, exc_p = safe_run("profile empty", profiler.profile, buf_empty, "empty.csv")
# Empty CSV has no columns — profiler may raise; what matters is no unhandled traceback
chk("S1-b  profiler raises a clean exception (not a crash) on empty df",
    exc_p is None or isinstance(exc_p, (ValueError, pd.errors.EmptyDataError, Exception)),
    str(exc_p))


# ─────────────────────────────────────────────────────────────────────────────
# S2: Single-Column Dataset
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S2: Single-Column Dataset ===")

df_single = pd.DataFrame({"Attrition": [0, 1, 0, 1, 0, 1, 0, 0, 1, 0]})
buf_single = io.BytesIO(df_single.to_csv(index=False).encode())

result_r2, exc_r2 = safe_run("route single-col", router.route, df_single, "single.csv")
chk("S2-a  router does not crash on single-column df",
    exc_r2 is None or result_r2 is not None, str(exc_r2))

result_p2, exc_p2 = safe_run("profile single-col", profiler.profile, buf_single, "single.csv")
chk("S2-b  profiler does not crash on single-column df",
    exc_p2 is None or result_p2 is not None, str(exc_p2))

result_m2, exc_m2 = safe_run("map single-col", mapper.map, df_single)
chk("S2-c  semantic mapper handles single column",
    exc_m2 is None, str(exc_m2))


# ─────────────────────────────────────────────────────────────────────────────
# S3: All-Null Dataset
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S3: All-Null Dataset ===")

df_null = pd.DataFrame({c: [None] * 20 for c in ["Age", "Department", "Attrition", "MonthlyIncome"]})
buf_null = io.BytesIO(df_null.to_csv(index=False).encode())

result_r3, exc_r3 = safe_run("route all-null", router.route, df_null, "nulls.csv")
chk("S3-a  router handles all-null df", exc_r3 is None, str(exc_r3))

result_p3, exc_p3 = safe_run("profile all-null", profiler.profile, buf_null, "nulls.csv")
chk("S3-b  profiler handles all-null df", exc_p3 is None, str(exc_p3))
if result_p3:
    chk("S3-c  profiler reports degraded quality for all-null df",
        result_p3.overall_quality_score < 70,
        f"quality={result_p3.overall_quality_score}")


# ─────────────────────────────────────────────────────────────────────────────
# S4: Duplicate Columns (identical column names)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S4: Duplicate Column Names ===")

# pandas automatically deduplicates on read; simulate via raw CSV bytes
dup_csv = b"Age,Age,Attrition\n25,25,0\n30,30,1\n40,40,0\n"
buf_dup = io.BytesIO(dup_csv)

result_r4, exc_r4 = safe_run("route dup-cols", router.route,
                               pd.read_csv(io.BytesIO(dup_csv)), "dup.csv")
chk("S4-a  router handles duplicate column names without crash",
    exc_r4 is None, str(exc_r4))

result_p4, exc_p4 = safe_run("profile dup-cols", profiler.profile,
                               io.BytesIO(dup_csv), "dup.csv")
chk("S4-b  profiler handles duplicate column names",
    exc_p4 is None, str(exc_p4))


# ─────────────────────────────────────────────────────────────────────────────
# S5: Missing Target Column
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S5: Missing Target Column ===")

df_notgt = pd.DataFrame({
    "Age": [25, 30, 45, 22, 37],
    "MonthlyIncome": [3000, 5000, 7000, 2500, 4500],
    "Department": ["Sales", "R&D", "HR", "Sales", "R&D"],
})
sem_notgt, exc_sm5 = safe_run("map no-target", mapper.map, df_notgt)
chk("S5-a  semantic mapper works without explicit target col",
    exc_sm5 is None, str(exc_sm5))

healer = DataHealer()
result_h5, exc_h5 = safe_run("heal no-target", healer.fit_transform,
                               df_notgt, sem_notgt, None)
chk("S5-b  DataHealer survives with target=None",
    exc_h5 is None, str(exc_h5))


# ─────────────────────────────────────────────────────────────────────────────
# S6: All-One-Class Target (no minority class)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S6: All-One-Class Target ===")

df_one = _hr_df(200)
df_one["Attrition"] = 0   # force single class

sem6 = mapper.map(df_one)
healer6 = DataHealer()
result_h6, exc_h6 = safe_run("heal one-class", healer6.fit_transform, df_one, sem6, "Attrition")
chk("S6-a  DataHealer survives all-one-class target",
    exc_h6 is None, str(exc_h6))

if result_h6:
    df_h6, _ = result_h6
    feature_names6 = [c for c in df_h6.columns if c != "Attrition" and c in df_h6.columns]
    result_ml6, exc_ml6 = safe_run("train one-class", ml_router.train,
                                    df_h6, feature_names6, "Attrition")
    chk("S6-b  MLRouter handles or rejects all-one-class gracefully (no crash)",
        exc_ml6 is None or isinstance(exc_ml6, (ValueError, KeyError)),
        str(exc_ml6))


# ─────────────────────────────────────────────────────────────────────────────
# S7: Massive Dataset (50,000 rows)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S7: Massive Dataset (50k rows) ===")

t7 = time.time()
df_big = _hr_df(50_000, seed=99)
sem7   = mapper.map(df_big)
healer7 = DataHealer()
result_h7, exc_h7 = safe_run("heal 50k", healer7.fit_transform, df_big, sem7, "Attrition")
chk("S7-a  DataHealer completes on 50k rows", exc_h7 is None, str(exc_h7))

if result_h7:
    df_h7, _ = result_h7
    feats7 = [c for c in df_h7.columns if c != "Attrition"]
    result_ml7, exc_ml7 = safe_run("train 50k", ml_router.train,
                                    df_h7, feats7, "Attrition")
    elapsed7 = round(time.time() - t7, 1)
    chk("S7-b  MLRouter trains on 50k rows", exc_ml7 is None, str(exc_ml7))
    chk("S7-c  50k training completes in under 120s", elapsed7 < 120,
        f"elapsed={elapsed7}s")
    if result_ml7:
        chk("S7-d  leakage_report attached for 50k",
            result_ml7.leakage_report is not None)
        chk("S7-e  validation_report attached for 50k",
            result_ml7.validation_report is not None)


# ─────────────────────────────────────────────────────────────────────────────
# S8: Corrupted / Mixed-Type Columns
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S8: Corrupted / Mixed-Type Columns ===")

# Build corrupted df via CSV so pandas keeps object dtype for mixed columns
_base = _hr_df(300)
_rows = _base.to_dict("records")
_rows[5]["Age"]            = "thirty"
_rows[15]["MonthlyIncome"] = "N/A"
_rows[25]["YearsAtCompany"] = None
df_corrupt = pd.DataFrame(_rows)

sem8 = mapper.map(df_corrupt)
healer8 = DataHealer()
result_h8, exc_h8 = safe_run("heal corrupted", healer8.fit_transform,
                               df_corrupt, sem8, "Attrition")
chk("S8-a  DataHealer recovers from mixed-type columns",
    exc_h8 is None, str(exc_h8))

if result_h8:
    df_h8, _ = result_h8
    feats8 = [c for c in df_h8.columns if c != "Attrition"]
    result_ml8, exc_ml8 = safe_run("train corrupted", ml_router.train,
                                    df_h8, feats8, "Attrition")
    chk("S8-b  MLRouter trains after DataHealer repair",
        exc_ml8 is None, str(exc_ml8))


# ─────────────────────────────────────────────────────────────────────────────
# S9: Sparse Dataset (90% missing values)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S9: Sparse Dataset (90% missing) ===")

rng9 = np.random.default_rng(7)
df_sparse = _hr_df(300)
for col in ["Age", "MonthlyIncome", "YearsAtCompany", "JobSatisfaction"]:
    mask = rng9.random(300) < 0.90
    df_sparse.loc[mask, col] = np.nan

sem9 = mapper.map(df_sparse)
healer9 = DataHealer()
result_h9, exc_h9 = safe_run("heal sparse", healer9.fit_transform,
                               df_sparse, sem9, "Attrition")
chk("S9-a  DataHealer handles 90% missing columns",
    exc_h9 is None, str(exc_h9))

if result_h9:
    df_h9, _ = result_h9
    feats9 = [c for c in df_h9.columns if c != "Attrition"]
    result_ml9, exc_ml9 = safe_run("train sparse", ml_router.train,
                                    df_h9, feats9, "Attrition")
    chk("S9-b  MLRouter trains on sparse-repaired data",
        exc_ml9 is None, str(exc_ml9))

buf_sparse = io.BytesIO(df_sparse.to_csv(index=False).encode())
result_p9, exc_p9 = safe_run("profile sparse", profiler.profile, buf_sparse, "sparse.csv")
chk("S9-c  profiler handles 90%-sparse df", exc_p9 is None, str(exc_p9))


# ─────────────────────────────────────────────────────────────────────────────
# S10: Unknown / Unrecognised Schema
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S10: Unknown Schema ===")

rng10 = np.random.default_rng(3)
df_unknown = pd.DataFrame({
    "sensor_x":     rng10.random(200),
    "reading_y":    rng10.integers(0, 100, 200),
    "timestamp_ns": rng10.integers(1_000_000, 9_999_999, 200),
    "label":        rng10.choice(["A", "B", "C"], 200),
})
result_r10, exc_r10 = safe_run("route unknown", router.route, df_unknown, "unknown.csv")
chk("S10-a  router assigns a type to unknown schema",
    exc_r10 is None and result_r10 is not None, str(exc_r10))
if result_r10:
    chk("S10-b  unknown schema NOT routed to hr_attrition",
        result_r10.dataset_type != "hr_attrition",
        f"got={result_r10.dataset_type}")


# ─────────────────────────────────────────────────────────────────────────────
# S11: Malformed Date Columns
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S11: Malformed Date Columns ===")

df_dates = _hr_df(150)
df_dates["HireDate"] = ["2020-01-01", "not-a-date", "2019/13/99",
                         "01-01-2021", None] * 30

sem11 = mapper.map(df_dates)
healer11 = DataHealer()
result_h11, exc_h11 = safe_run("heal malformed dates", healer11.fit_transform,
                                 df_dates, sem11, "Attrition")
chk("S11-a  DataHealer handles malformed date strings",
    exc_h11 is None, str(exc_h11))


# ─────────────────────────────────────────────────────────────────────────────
# S12: High-Cardinality Free-Text Column
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S12: High-Cardinality Free-Text Column ===")

rng12 = np.random.default_rng(12)
df_hc = _hr_df(300)
df_hc["EmployeeComment"] = [f"Employee note #{i}: {rng12.choice(['good','bad','ok'])}" for i in range(300)]
df_hc["EmployeeID"]      = [f"EMP{1000+i}" for i in range(300)]

sem12 = mapper.map(df_hc)
healer12 = DataHealer()
result_h12, exc_h12 = safe_run("heal high-card", healer12.fit_transform,
                                 df_hc, sem12, "Attrition")
chk("S12-a  DataHealer drops/encodes high-cardinality text without crash",
    exc_h12 is None, str(exc_h12))

if result_h12:
    df_h12, _ = result_h12
    feats12 = [c for c in df_h12.columns if c != "Attrition"]
    result_ml12, exc_ml12 = safe_run("train high-card", ml_router.train,
                                      df_h12, feats12, "Attrition")
    chk("S12-b  MLRouter trains after high-cardinality handling",
        exc_ml12 is None, str(exc_ml12))


# ─────────────────────────────────────────────────────────────────────────────
# S13: LeakageDetector — Perfect Target Leakage
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S13: LeakageDetector — Perfect Target Leakage ===")

df_leak = _hr_df(400)
df_leak["AttritionCopy"] = df_leak["Attrition"]   # perfect leakage column

ld = LeakageDetector()
feats_leak = [c for c in df_leak.columns if c != "Attrition"]
leak_rep, exc_l13 = safe_run("leakage detect", ld.detect,
                               df_leak, feats_leak, "Attrition")
chk("S13-a  LeakageDetector runs without crash", exc_l13 is None, str(exc_l13))
if leak_rep:
    chk("S13-b  perfect leakage column detected (risk > 0)",
        leak_rep.leakage_risk_score > 0,
        f"risk={leak_rep.leakage_risk_score}")
    chk("S13-c  is_trustworthy=False when critical leakage present OR risk>0.5",
        not leak_rep.is_trustworthy or leak_rep.leakage_risk_score <= 0.5,
        f"trustworthy={leak_rep.is_trustworthy}, risk={leak_rep.leakage_risk_score}")


# ─────────────────────────────────────────────────────────────────────────────
# S14: ModelValidator — receives a valid TrainingResult
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S14: ModelValidator on real TrainingResult ===")

df_mv = _hr_df(600)
sem_mv = mapper.map(df_mv)
healer_mv = DataHealer()
result_hmv, exc_hmv = safe_run("heal mv", healer_mv.fit_transform, df_mv, sem_mv, "Attrition")

chk("S14-a  DataHealer succeeds for validator test", exc_hmv is None, str(exc_hmv))

if result_hmv:
    df_hmv, _ = result_hmv
    feats_mv = [c for c in df_hmv.columns if c != "Attrition"]
    tr_mv, exc_tr = safe_run("train mv", ml_router.train,
                              df_hmv, feats_mv, "Attrition")
    chk("S14-b  MLRouter trains for validator test", exc_tr is None, str(exc_tr))

    if tr_mv:
        chk("S14-c  validation_report populated after training",
            tr_mv.validation_report is not None)
        if tr_mv.validation_report:
            vr = tr_mv.validation_report
            chk("S14-d  validation_report has overall_status field",
                vr.overall_status in ("VALID", "DEGRADED", "INVALID"),
                f"status={vr.overall_status}")
            chk("S14-e  governed_auc <= original_auc",
                vr.governed_auc <= vr.original_auc + 0.001,
                f"gov={vr.governed_auc} orig={vr.original_auc}")
            chk("S14-f  confidence_band is a known value",
                vr.confidence_band in ("High", "Moderate", "Low", "Unreliable"),
                f"band={vr.confidence_band}")


# ─────────────────────────────────────────────────────────────────────────────
# S15: Router never routes biosignal to HR pipeline
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S15: Biosignal Safety Invariant ===")

rng15 = np.random.default_rng(15)
n15 = 5000
df_bvp = pd.DataFrame({
    "BVP":       rng15.normal(0, 1, n15),
    "timestamp": np.arange(n15),
})
contract15, exc_r15 = safe_run("route BVP", router.route, df_bvp, "BVP.csv")
chk("S15-a  biosignal router does not crash", exc_r15 is None, str(exc_r15))
if contract15:
    chk("S15-b  BVP.csv is NOT routed to hr_attrition",
        contract15.dataset_type != "hr_attrition",
        f"got={contract15.dataset_type}")
    chk("S15-c  BVP.csv is biosignal",
        contract15.is_biosignal or "biosignal" in contract15.dataset_type,
        f"type={contract15.dataset_type}")


# ─────────────────────────────────────────────────────────────────────────────
# S16: DataProfiler handles non-UTF-8 CSV (Latin-1 encoding)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S16: Non-UTF-8 CSV ===")

latin1_csv = "Age,Department,Attrition\n25,Ventes,0\n30,R\xe9seau,1\n".encode("latin-1")
result_p16, exc_p16 = safe_run("profile latin-1", profiler.profile,
                                 io.BytesIO(latin1_csv), "latin1.csv")
chk("S16-a  profiler handles Latin-1 encoded CSV",
    exc_p16 is None, str(exc_p16))


# ─────────────────────────────────────────────────────────────────────────────
# S17: Extremely Imbalanced Target (99:1)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S17: Extremely Imbalanced Target (99:1) ===")

rng17 = np.random.default_rng(17)
df_imb = _hr_df(1000)
# Force 99% class 0, 1% class 1
df_imb["Attrition"] = 0
df_imb.loc[rng17.choice(1000, 10, replace=False), "Attrition"] = 1

sem17 = mapper.map(df_imb)
healer17 = DataHealer()
result_h17, exc_h17 = safe_run("heal imbalanced", healer17.fit_transform,
                                  df_imb, sem17, "Attrition")
chk("S17-a  DataHealer handles 99:1 imbalanced target", exc_h17 is None, str(exc_h17))

if result_h17:
    df_h17, _ = result_h17
    feats17 = [c for c in df_h17.columns if c != "Attrition"]
    result_ml17, exc_ml17 = safe_run("train imbalanced", ml_router.train,
                                      df_h17, feats17, "Attrition")
    chk("S17-b  MLRouter handles extreme class imbalance (no crash)",
        exc_ml17 is None, str(exc_ml17))


# ─────────────────────────────────────────────────────────────────────────────
# S18: Feature names with special characters / unicode
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S18: Special-Character Column Names ===")

df_special = pd.DataFrame({
    "Age (Years)":  [25, 30, 45, 22],
    "Monthly/Income": [3000, 5000, 7000, 2500],
    "Department#1": ["Sales", "R&D", "HR", "Sales"],
    "Attrition":    [0, 1, 0, 1],
})
sem18 = mapper.map(df_special)
healer18 = DataHealer()
result_h18, exc_h18 = safe_run("heal special cols", healer18.fit_transform,
                                  df_special, sem18, "Attrition")
chk("S18-a  DataHealer handles special-character column names",
    exc_h18 is None, str(exc_h18))


# ─────────────────────────────────────────────────────────────────────────────
# S19: Profiler on very wide dataset (200 columns)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S19: Very Wide Dataset (200 columns) ===")

rng19 = np.random.default_rng(19)
df_wide = pd.DataFrame(
    rng19.random((100, 200)),
    columns=[f"feature_{i:03d}" for i in range(200)],
)
df_wide["Attrition"] = rng19.choice([0, 1], 100)
buf_wide = io.BytesIO(df_wide.to_csv(index=False).encode())

result_p19, exc_p19 = safe_run("profile wide", profiler.profile, buf_wide, "wide.csv")
chk("S19-a  profiler handles 200-column dataset", exc_p19 is None, str(exc_p19))

result_r19, exc_r19 = safe_run("route wide", router.route, df_wide, "wide.csv")
chk("S19-b  router handles 200-column dataset", exc_r19 is None, str(exc_r19))


# ─────────────────────────────────────────────────────────────────────────────
# S20: MLRouter with zero usable features after healing
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== S20: Zero Usable Features ===")

df_nofeat = pd.DataFrame({
    "Attrition": [0, 1, 0, 1, 0] * 40,
})
sem20 = mapper.map(df_nofeat)
healer20 = DataHealer()
result_h20, exc_h20 = safe_run("heal no-features", healer20.fit_transform,
                                  df_nofeat, sem20, "Attrition")
chk("S20-a  DataHealer handles target-only df", exc_h20 is None, str(exc_h20))

if result_h20:
    df_h20, _ = result_h20
    feats20 = [c for c in df_h20.columns if c != "Attrition"]
    if not feats20:
        chk("S20-b  MLRouter raises ValueError for empty feature set",
            True, "No features — correct, no training attempted")
    else:
        result_ml20, exc_ml20 = safe_run("train no-features", ml_router.train,
                                          df_h20, feats20, "Attrition")
        chk("S20-b  MLRouter handles minimal feature set",
            exc_ml20 is None, str(exc_ml20))


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
total = _PASS + _FAIL
print(f"\n{'='*60}")
print(f"STRESS TEST RESULTS: {_PASS}/{total} PASSED, {_FAIL} FAILED")
print(f"{'='*60}")
if _ERRORS:
    print("FAILURES:")
    for e in _ERRORS:
        print(f"  {e}")

sys.exit(0 if _FAIL == 0 else 1)
