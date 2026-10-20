"""
Adaptive Router v2 — High-Precision Dataset Classification & Contract Generation

Produces a DatasetContract for every uploaded file. The contract governs ALL
downstream rendering — no dashboard runs before reading it.

Classification pipeline (4 stages):
  1. Filename-based hard rules (HR.csv / BVP.csv → biosignal_timeseries, confidence=0.99)
  2. Column-name signal scoring with weighted keywords
  3. Value-distribution heuristics (Likert, binary flag, large numeric, datetime density)
  4. Conflict resolution + subtype labelling

Critical invariant: biosignal datasets ALWAYS produce row_unit="signal_samples"
and block all employee-level metrics at the contract level.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

from .dataset_contract import (
    DatasetContract, build_contract,
    DATASET_TYPES, ROW_UNITS,
)
from .modality_classifier import ModalityClassifier, ModalityResult, Modality
from .dataset_confidence_engine import DatasetConfidenceEngine, RoutingConfidence
from .semantic_column_mapper import SemanticColumnMapper, SemanticMapping
from .fail_safe_guardrails import SandboxValidator, SandboxReport
from .telemetry_engine import TelemetryEngine, hash_dataframe

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — FILENAME HARD RULES
# ─────────────────────────────────────────────────────────────────────────────

# Maps filename stem (lowercase, no extension) → (dataset_type, subtype, signal_type, confidence)
_FILENAME_RULES: Dict[str, Tuple[str, str, str, float]] = {
    # WESAD / Empatica wearable signals
    "hr":    ("biosignal_timeseries", "wesad_hr",    "HR",   0.99),
    "eda":   ("biosignal_timeseries", "wesad_eda",   "EDA",  0.99),
    "bvp":   ("biosignal_timeseries", "wesad_bvp",   "BVP",  0.99),
    "temp":  ("biosignal_timeseries", "wesad_temp",  "TEMP", 0.99),
    "acc":   ("biosignal_timeseries", "wesad_acc",   "ACC",  0.99),
    "ibi":   ("biosignal_timeseries", "wesad_ibi",   "IBI",  0.99),
    # Generic signal names
    "signal":     ("biosignal_timeseries", "generic_signal", "unknown", 0.85),
    "physio":     ("biosignal_timeseries", "physiological",  "unknown", 0.85),
    "wearable":   ("biosignal_timeseries", "wearable",       "unknown", 0.85),
    "empatica":   ("biosignal_timeseries", "empatica",       "unknown", 0.85),
    "ecg":        ("biosignal_timeseries", "ecg_signal",     "ECG",    0.95),
    "eeg":        ("biosignal_timeseries", "eeg_signal",     "EEG",    0.95),
    "ppg":        ("biosignal_timeseries", "ppg_signal",     "PPG",    0.95),
}

# Filename substrings that also trigger biosignal
_BIOSIGNAL_FILENAME_PATTERNS = [
    r"wesad", r"empatica", r"e4_", r"_sensor", r"wearable",
    r"physio", r"biometric", r"galvanic", r"skin_cond",
]

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — COLUMN KEYWORD SCORING
# ─────────────────────────────────────────────────────────────────────────────

# (dataset_type, keywords, weight_per_hit, min_hits_for_contribution)
_COLUMN_SIGNALS: List[Tuple[str, List[str], float, int]] = [
    # Attrition — very specific
    ("hr_attrition", [
        "attrition", "turnover", "left", "resigned", "quit", "churn",
        "terminated", "separated", "exit_flag", "voluntary_exit",
    ], 3.0, 1),

    # Biosignal — physical sensor columns
    ("biosignal_timeseries", [
        "eda", "bvp", "ibi", "hrv", "gsr", "ecg", "eeg", "emg",
        "skin_conductance", "galvanic", "blood_volume", "inter_beat",
        "rr_interval", "nn_interval", "ppg", "accelerometer",
    ], 4.0, 1),
    # Heart-rate columns are STRONG biosignal signal
    ("biosignal_timeseries", [
        "heart_rate", "heartrate",
    ], 3.5, 1),
    # Ambiguous short names (hr, acc, temp) — lower weight, need HR.csv filename to confirm
    ("biosignal_timeseries", [
        " hr ", "bpm", "pulse_rate", "skin_temp",
    ], 2.0, 1),

    # HR workforce
    ("hr_workforce", [
        "department", "job_level", "education", "marital", "gender",
        "yearsatcompany", "years_at_company", "monthlyincome", "monthly_income",
        "jobrole", "job_role", "businesstravel",
    ], 2.0, 2),

    # Psychological survey
    ("psychological_survey", [
        "burnout", "exhaustion", "cynicism", "efficacy",
        "anxiety", "depression", "resilience", "coping",
        "perceived_stress", "job_strain", "emotional_labor",
    ], 2.5, 2),

    # Engagement survey
    ("psychological_survey", [
        "engagement", "satisfaction", "commitment", "motivation",
        "job_satisfaction", "work_life_balance", "environment_satisfaction",
    ], 1.5, 3),

    # Time series
    ("generic_timeseries", [
        "timestamp", "datetime", "date", "month", "year",
        "period", "week", "quarter",
    ], 1.5, 2),

    # Productivity
    ("productivity_logs", [
        "tasks", "tickets", "commits", "output", "throughput",
        "sprint", "velocity", "utilization",
    ], 2.0, 2),

    # Compensation
    ("compensation_dataset", [
        "salary", "wage", "pay", "compensation", "bonus", "equity",
        "total_comp", "base_pay",
    ], 2.0, 3),
]

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — VALUE HEURISTICS
# ─────────────────────────────────────────────────────────────────────────────

def _value_heuristics(df: pd.DataFrame) -> Dict[str, float]:
    """Score dataset types based on value distributions."""
    scores: Dict[str, float] = {}
    n = len(df)
    if n == 0:
        return scores

    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    obj_cols = df.select_dtypes(include=["object"]).columns.tolist()

    # Single long numeric column → likely sensor signal
    if len(df.columns) <= 3 and len(num_cols) >= 1:
        main = df[num_cols[0]].dropna()
        if len(main) > 1000:
            # Check if values look like a signal (continuous, not categorical)
            uq_rate = main.nunique() / len(main)
            if uq_rate > 0.50:
                scores["biosignal_timeseries"] = scores.get("biosignal_timeseries", 0) + 3.0

    # Binary Yes/No in object column → possible HR attrition target
    for col in obj_cols[:10]:
        vals = set(str(v).strip().lower() for v in df[col].dropna().unique())
        if vals <= {"yes", "no", "y", "n"} and df[col].notna().mean() > 0.7:
            scores["hr_attrition"] = scores.get("hr_attrition", 0) + 2.0

    # Many Likert-scale columns → survey
    likert_count = 0
    for col in num_cols[:20]:
        s = df[col].dropna()
        if len(s) > 10 and s.min() >= 1 and s.max() <= 7 and s.nunique() <= 7:
            if (s == s.round()).mean() > 0.95:
                likert_count += 1
    if likert_count >= 4:
        scores["psychological_survey"] = scores.get("psychological_survey", 0) + likert_count * 0.5

    # Dense datetime column → time series
    date_col_count = 0
    for col in df.columns[:10]:
        sample = df[col].dropna().head(50).astype(str)
        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() > 0.80:
            date_col_count += 1
    if date_col_count > 0:
        scores["generic_timeseries"] = scores.get("generic_timeseries", 0) + date_col_count * 1.0

    return scores


# ─────────────────────────────────────────────────────────────────────────────
# TARGET DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_TARGET_KEYWORDS = [
    "attrition", "turnover", "churn", "resigned", "exit",
    "outcome", "target", "label", "result", "status",
    "hired", "promoted", "fired", "terminated", "separated",
]
# Short exact-match-only keywords (must equal the full column name, lowercased)
_TARGET_EXACT_KEYWORDS = {"y", "left", "churn"}

_TARGET_POSITIVE_VALUES = {
    "yes", "y", "1", "true", "t", "left", "resigned", "churned",
    "terminated", "separated", "attrited", "exit",
}


def _detect_target(df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
    candidates: List[Tuple[str, float]] = []
    for col in df.columns:
        cl = col.lower().strip()
        score = 0.0
        # Exact-match for short/ambiguous keywords
        if cl in _TARGET_EXACT_KEYWORDS:
            score += 2.0
        # Substring match for longer, unambiguous keywords
        for kw in _TARGET_KEYWORDS:
            if kw in cl:
                score += 1.0
        if score == 0:
            continue
        s = df[col].dropna()
        nu = s.nunique()
        if nu == 2:
            score += 2.0
            vals = set(str(v).lower().strip() for v in s.unique())
            if vals & _TARGET_POSITIVE_VALUES:
                score += 1.0
        elif 2 < nu <= 10:
            score += 0.5
        candidates.append((col, score))

    candidates.sort(key=lambda x: x[1], reverse=True)
    if candidates and candidates[0][1] >= 1.0:
        return True, candidates[0][0]
    return False, None


# ─────────────────────────────────────────────────────────────────────────────
# EMPLOYEE / SIGNAL COLUMN DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

_HR_EMPLOYEE_KEYWORDS = [
    "department", "dept", "age", "gender", "sex", "education", "tenure",
    "years_at", "salary", "income", "wage", "pay", "compensation",
    "job_level", "job_role", "marital", "performance", "rating",
    "overtime", "workload", "manager", "training", "promotion",
    "distance", "team", "division", "business_unit",
]

_BIOSIGNAL_KEYWORDS = [
    "hr", "eda", "bvp", "temp", "acc", "ibi", "ecg", "eeg", "emg", "ppg",
    "heart_rate", "heart rate", "bpm", "skin_conductance", "galvanic",
    "blood_volume", "accelerometer", "gyroscope", "temperature",
    "inter_beat", "rr_interval", "hrv",
]


def _detect_column_groups(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Return (employee_cols, signal_cols) lists."""
    emp_cols: List[str] = []
    sig_cols: List[str] = []
    for col in df.columns:
        cl = col.lower().replace(" ", "_")
        if any(kw in cl for kw in _BIOSIGNAL_KEYWORDS):
            sig_cols.append(col)
        elif any(kw in cl for kw in _HR_EMPLOYEE_KEYWORDS):
            emp_cols.append(col)
    return emp_cols, sig_cols


def _detect_subject_id(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        cl = col.lower()
        if any(kw in cl for kw in ["employee_id", "emp_id", "id", "subject", "worker_id"]):
            if df[col].nunique(dropna=True) / max(len(df[col].dropna()), 1) > 0.8:
                return col
    return None


def _detect_time_col(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        cl = col.lower()
        if any(kw in cl for kw in ["date", "time", "timestamp", "datetime", "month", "year"]):
            try:
                parsed = pd.to_datetime(df[col].head(50), errors="coerce", infer_datetime_format=True)
                if parsed.notna().mean() > 0.70:
                    return col
            except Exception:
                pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL TYPE DETECTOR (for biosignal datasets)
# ─────────────────────────────────────────────────────────────────────────────

_SIGNAL_SYNONYMS: Dict[str, str] = {
    # HR
    "hr": "HR", "heart_rate": "HR", "heartrate": "HR", "bpm": "HR",
    "pulse": "HR", "heart rate": "HR",
    # EDA
    "eda": "EDA", "gsr": "EDA", "skin_conductance": "EDA",
    "electrodermal": "EDA", "galvanic": "EDA",
    # BVP
    "bvp": "BVP", "blood_volume_pulse": "BVP", "ppg": "BVP",
    # TEMP
    "temp": "TEMP", "temperature": "TEMP", "skin_temp": "TEMP",
    "body_temperature": "TEMP",
    # ACC
    "acc": "ACC", "accelerometer": "ACC", "accel": "ACC",
    "motion": "ACC",
    # IBI
    "ibi": "IBI", "rr_interval": "IBI", "nn_interval": "IBI",
    "inter_beat": "IBI",
    # ECG / EEG
    "ecg": "ECG", "eeg": "EEG", "emg": "EMG",
}

_FILENAME_TO_SIGNAL = {
    "hr": "HR", "eda": "EDA", "bvp": "BVP", "temp": "TEMP",
    "acc": "ACC", "ibi": "IBI", "ecg": "ECG", "eeg": "EEG",
    "emg": "EMG", "ppg": "PPG",
}


def _detect_signal_type(df: pd.DataFrame, filename: str) -> Optional[str]:
    stem = re.sub(r"\.(csv|xlsx|txt|dat)$", "", filename.lower().strip())
    if stem in _FILENAME_TO_SIGNAL:
        return _FILENAME_TO_SIGNAL[stem]
    for col in df.columns:
        cl = col.lower().strip().replace(" ", "_")
        if cl in _SIGNAL_SYNONYMS:
            return _SIGNAL_SYNONYMS[cl]
        for syn, canon in _SIGNAL_SYNONYMS.items():
            if syn in cl:
                return canon
    return None


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY SCORING (context-aware)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_quality(df: pd.DataFrame, dataset_type: str) -> Tuple[float, List[str]]:
    issues: List[str] = []
    score = 100.0

    # Universal
    n = len(df)
    miss_overall = df.isna().mean().mean()
    if miss_overall > 0.40:
        score -= 30
        issues.append(f"High overall missing rate: {miss_overall:.0%}")
    elif miss_overall > 0.20:
        score -= 15
        issues.append(f"Moderate missing rate: {miss_overall:.0%}")

    dup_rate = df.duplicated().mean()
    if dup_rate > 0.05:
        score -= 10
        issues.append(f"Duplicate rows: {dup_rate:.1%}")

    if n < 50:
        score -= 30
        issues.append(f"Very small dataset: {n} rows")
    elif n < 200:
        score -= 10
        issues.append(f"Small dataset: {n} rows")

    if dataset_type == "biosignal_timeseries":
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0:
            score -= 40
            issues.append("No numeric signal columns found")
        else:
            for col in num_cols:
                s = df[col].dropna()
                if len(s) > 10:
                    # Flatline detection
                    if s.std() < 1e-6:
                        score -= 20
                        issues.append(f"Flatline detected in '{col}'")
                    # Extreme spike check
                    zmax = abs((s - s.mean()) / (s.std() + 1e-9)).max()
                    if zmax > 10:
                        score -= 5
                        issues.append(f"Extreme spikes in '{col}' (z={zmax:.0f})")

    elif dataset_type in ("hr_attrition", "hr_workforce"):
        required = ["age", "department", "salary", "tenure", "performance"]
        col_lower = " ".join(df.columns).lower()
        missing_req = [r for r in required if r not in col_lower]
        if missing_req:
            score -= len(missing_req) * 3
            issues.append(f"Missing typical HR columns: {missing_req}")

    score = max(0.0, min(100.0, score))
    return round(score, 1), issues


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE DESCRIPTIONS
# ─────────────────────────────────────────────────────────────────────────────

_PIPELINE_DESCRIPTIONS: Dict[str, Tuple[str, str]] = {
    "hr_attrition": (
        "HR Attrition ML Pipeline",
        "Supervised attrition prediction with CatBoost/XGBoost/LightGBM/RF/LR ensemble, "
        "SHAP explainability, psychological construct estimation, department risk analysis, "
        "financial exposure modelling, and executive PDF/Excel reports.",
    ),
    "hr_workforce": (
        "HR Workforce Analytics Pipeline",
        "Workforce profiling, construct estimation, burnout/engagement dashboards, "
        "and department stability analysis (no supervised attrition model without target).",
    ),
    "psychological_survey": (
        "Psychological Survey Intelligence Pipeline",
        "Latent construct estimation (burnout, engagement, resilience) grounded in "
        "JD-R / COR / Maslach theory. Wellbeing profiling and psychological risk dashboard.",
    ),
    "burnout_survey": (
        "Burnout Survey Analysis Pipeline",
        "MBI-style construct scoring: emotional exhaustion, cynicism, personal efficacy. "
        "Burnout hotspot detection and organisational risk profiling.",
    ),
    "biosignal_timeseries": (
        "Biosignal / Physiological Signal Analysis Pipeline",
        "Window-based feature extraction, stress/fatigue proxy scoring, HRV analysis, "
        "anomaly detection, and physiological risk timeline. "
        "Rows are signal samples — NOT employees. No HR employee metrics.",
    ),
    "generic_timeseries": (
        "Generic Time-Series Intelligence Pipeline",
        "Trend detection, anomaly detection, bootstrap confidence-band forecasting, "
        "and risk escalation scoring.",
    ),
    "productivity_logs": (
        "Productivity Analytics Pipeline",
        "Output trend analysis, anomaly detection, and forecasting.",
    ),
    "compensation_dataset": (
        "Compensation Analytics Pipeline",
        "Salary distribution, equity analysis, and benchmarking.",
    ),
    "mixed_enterprise": (
        "Multi-Domain Adaptive Pipeline",
        "Hybrid HR + time-series + generic ML analysis. "
        "Results interpreted with caution given mixed dataset signals.",
    ),
    "unknown": (
        "Dataset Intelligence & Profiling",
        "Dataset type could not be determined. Provides data quality report, "
        "semantic column mapping, and recommendations for missing fields.",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

class DatasetClassifier:
    """Classifies a DataFrame into a dataset_type with confidence."""

    def classify(self,
                 df: pd.DataFrame,
                 filename: str = "") -> Tuple[str, str, float, Optional[str]]:
        """Returns (dataset_type, subtype, confidence, detected_signal_type)."""
        stem = re.sub(r"\.(csv|xlsx|txt|dat|json|parquet)$", "",
                      filename.lower().strip())

        # ── Stage 1: filename hard rules ─────────────────────────────────────
        if stem in _FILENAME_RULES:
            dtype, subtype, sig_type, conf = _FILENAME_RULES[stem]
            return dtype, subtype, conf, sig_type

        # Check biosignal filename patterns
        for pat in _BIOSIGNAL_FILENAME_PATTERNS:
            if re.search(pat, filename.lower()):
                sig = _detect_signal_type(df, filename)
                return "biosignal_timeseries", "biosignal_pattern", 0.90, sig

        # ── Stage 2: column keyword scoring ──────────────────────────────────
        col_text = " ".join(df.columns).lower()
        type_scores: Dict[str, float] = {}

        for dtype, keywords, weight, min_hits in _COLUMN_SIGNALS:
            # Word-boundary matching prevents "month" matching inside "monthlyincome",
            # "year" inside "yearsatcompany", etc.
            hits = sum(
                1 for kw in keywords
                if re.search(r'\b' + re.escape(kw) + r'\b', col_text)
            )
            if hits >= min_hits:
                type_scores[dtype] = type_scores.get(dtype, 0) + hits * weight

        # ── Stage 3: value heuristics ─────────────────────────────────────────
        heuristic_scores = _value_heuristics(df)
        for dt, hs in heuristic_scores.items():
            type_scores[dt] = type_scores.get(dt, 0) + hs

        # ── Biosignal tie-break: biosignal always wins over workforce if present
        if type_scores.get("biosignal_timeseries", 0) > 0:
            bio_s = type_scores["biosignal_timeseries"]
            hr_s  = type_scores.get("hr_attrition", 0) + type_scores.get("hr_workforce", 0)
            if bio_s >= hr_s * 0.5:
                sig = _detect_signal_type(df, filename)
                return "biosignal_timeseries", "column_detected", \
                       min(0.95, bio_s / max(sum(type_scores.values()), 1)), sig

        if not type_scores:
            return "unknown", "unknown", 0.30, None

        best    = max(type_scores, key=type_scores.get)
        total   = sum(type_scores.values())
        conf    = min(0.97, type_scores[best] / max(total, 1))

        # Consolidate HR subtypes FIRST — before any mixed-enterprise decision
        # hr_workforce + hr_attrition both scoring = clearly an HR dataset
        if best in ("hr_workforce", "mixed_enterprise"):
            if type_scores.get("hr_attrition", 0) > 0 and type_scores.get("hr_workforce", 0) > 0:
                best = "hr_attrition"
            elif best == "hr_workforce" and type_scores.get("hr_attrition", 0) > 0:
                best = "hr_attrition"

        # Mixed if top-2 are very close AND they are NOT both HR family types
        sorted_s = sorted(type_scores.values(), reverse=True)
        if len(sorted_s) >= 2 and (sorted_s[0] - sorted_s[1]) < sorted_s[0] * 0.20:
            if best != "biosignal_timeseries":
                top2_types = sorted(type_scores, key=type_scores.get, reverse=True)[:2]
                # HR attrition + HR workforce being close = still an HR dataset, not mixed
                if not set(top2_types) <= {"hr_attrition", "hr_workforce"}:
                    best = "mixed_enterprise"

        return best, best, round(conf, 3), None


# ─────────────────────────────────────────────────────────────────────────────
# ADAPTIVE ROUTER (public API)
# ─────────────────────────────────────────────────────────────────────────────

class AdaptiveRouter:
    """
    Produces a DatasetContract for any uploaded DataFrame.

    Usage
    -----
    router = AdaptiveRouter()
    contract = router.route(df, filename="BVP.csv")
    # contract.is_biosignal → True
    # contract.row_unit     → "signal_samples"
    # contract.blocks("attrition_prediction") → True

    Phase 3: Now also runs ModalityClassifier, DatasetConfidenceEngine,
    SemanticColumnMapper, and stores their results in the contract for
    downstream sandbox validation.
    """

    def __init__(self):
        self._clf         = DatasetClassifier()
        self._modality    = ModalityClassifier()
        self._conf_engine = DatasetConfidenceEngine()
        self._sem_mapper  = SemanticColumnMapper()
        self._sandbox     = SandboxValidator()

    def route(self,
              df: pd.DataFrame,
              filename: str = "",
              user_override_type: Optional[str] = None) -> DatasetContract:

        if user_override_type and user_override_type in DATASET_TYPES:
            dtype, subtype, confidence = user_override_type, user_override_type, 1.0
            sig_type = _detect_signal_type(df, filename)
        else:
            dtype, subtype, confidence, sig_type = self._clf.classify(df, filename)

        # Fallback signal type from columns
        if dtype == "biosignal_timeseries" and sig_type is None:
            sig_type = _detect_signal_type(df, filename)

        # Structural info
        target_available, target_col = _detect_target(df)
        subject_id_col = _detect_subject_id(df)
        time_col       = _detect_time_col(df)
        emp_cols, sig_cols = _detect_column_groups(df)

        # For biosignal: numeric columns ARE the signal columns
        if dtype == "biosignal_timeseries" and not sig_cols:
            num_cols = df.select_dtypes(include=["number"]).columns.tolist()
            sig_cols = num_cols[:5]

        # Quality
        quality_score, quality_issues = _compute_quality(df, dtype)

        # Pipeline description
        pipe_name, pipe_desc = _PIPELINE_DESCRIPTIONS.get(
            dtype, _PIPELINE_DESCRIPTIONS["unknown"]
        )

        # Build reason string
        reason = f"Classified as '{dtype}' (confidence={confidence:.0%}). {pipe_desc[:120]}…"

        # Warnings
        warnings: List[str] = []
        if quality_score < 60:
            warnings.append(f"Data quality score is {quality_score:.0f}/100 — results may be unreliable.")

        # ── Phase 3: Run new universal architecture engines ────────────────────
        modality_result   = None
        routing_conf      = None
        semantic_map_v2   = None
        sandbox_report_obj = None

        try:
            modality_result = self._modality.classify(df, filename)

            # Augment warnings from modality caveats
            for cav in (modality_result.caveats or []):
                if cav not in warnings and len(warnings) < 6:
                    warnings.append(f"[Modality] {cav}")

            # Cross-check: if modality classifier disagrees with stage-1/2 classifier
            # on biosignal, the modality classifier's hard rules take priority
            if (modality_result.modality == Modality.BIOSIGNAL and
                    dtype != "biosignal_timeseries" and
                    modality_result.confidence >= 0.80):
                dtype = "biosignal_timeseries"
                subtype = modality_result.sub_modality
                confidence = modality_result.confidence
                sig_type = modality_result.signal_type_hint or sig_type
                target_available = False
                target_col = None
                emp_cols = []
                warnings.append(
                    "[Modality Classifier] Overriding routing to biosignal_timeseries — "
                    f"high-confidence biosignal evidence ({modality_result.confidence:.0%})."
                )

        except Exception as _e:
            logger.warning(f"ModalityClassifier failed: {_e}")

        try:
            semantic_map_v2 = self._sem_mapper.map(df)
            for cav in (semantic_map_v2.caveats or []):
                if "biosignal AND HR" in cav and cav not in warnings:
                    warnings.append(f"[SemanticMapper] {cav}")
        except Exception as _e:
            logger.warning(f"SemanticColumnMapper failed: {_e}")

        try:
            miss_overall = float(df.isna().mean().mean())
            sem_col_scores = None
            if semantic_map_v2:
                from .semantic_column_mapper import SemanticRole
                role_counts: Dict[str, int] = {}
                _cols = getattr(semantic_map_v2, "columns", None) or {}
                for cm in _cols.values():
                    _role_val = cm.role.value if hasattr(cm.role, "value") else str(cm.role)
                    role_counts[_role_val] = role_counts.get(_role_val, 0) + 1
                n_cols_total = max(len(df.columns), 1)
                sem_col_scores = {k: v / n_cols_total for k, v in role_counts.items()}

            if modality_result:
                routing_conf = self._conf_engine.score(
                    modality_result=modality_result,
                    df=df,
                    filename=filename,
                    missing_rate_overall=miss_overall,
                    semantic_col_scores=sem_col_scores,
                )
                # If routing is locked (hard rule) use locked confidence
                if routing_conf.routing_locked:
                    confidence = routing_conf.overall_confidence
        except Exception as _e:
            logger.warning(f"DatasetConfidenceEngine failed: {_e}")

        try:
            if modality_result and routing_conf:
                ctx = {
                    "target_available": target_available,
                    "target_column": target_col,
                    "feature_columns": emp_cols + sig_cols,
                    "missing_rate_overall": float(df.isna().mean().mean()),
                    "has_department_column": any(
                        "department" in c.lower() or "division" in c.lower()
                        for c in df.columns
                    ),
                    "has_temporal_column": time_col is not None,
                    "semantic_mapping": semantic_map_v2,
                }
                sandbox_report_obj = self._sandbox.validate_all(
                    modality_result=modality_result,
                    routing_conf=routing_conf,
                    df=df,
                    ctx=ctx,
                )
                for failure in (sandbox_report_obj.critical_failures or []):
                    if failure not in warnings:
                        warnings.append(f"[CRITICAL] {failure}")
        except Exception as _e:
            logger.warning(f"SandboxValidator failed: {_e}")

        contract = build_contract(
            dataset_type         = dtype,
            dataset_subtype      = subtype,
            confidence           = confidence,
            target_available     = target_available if dtype != "biosignal_timeseries" else False,
            target_column        = target_col if dtype != "biosignal_timeseries" else None,
            subject_id_column    = subject_id_col,
            time_column          = time_col,
            signal_columns       = sig_cols,
            employee_columns     = emp_cols if dtype != "biosignal_timeseries" else [],
            recommended_pipeline = pipe_name,
            reason               = reason,
            warning_messages     = warnings,
            detected_signal_type = sig_type,
            quality_score        = quality_score,
            quality_issues       = quality_issues,
        )

        # ── Attach Phase 3 results to contract ────────────────────────────────
        contract.modality_result   = modality_result
        contract.routing_confidence = routing_conf
        contract.semantic_map_v2   = semantic_map_v2
        contract.sandbox_report    = sandbox_report_obj

        logger.info(
            "Contract: type=%s subtype=%s conf=%.0f%% row_unit=%s target=%s "
            "biosignal=%s signal_type=%s quality=%.0f",
            dtype, subtype, confidence * 100, contract.row_unit,
            target_col, contract.is_biosignal, sig_type, quality_score,
        )
        return contract

    def validate_sandbox(
        self,
        contract: DatasetContract,
        df: pd.DataFrame,
        target_available: bool = False,
        target_column: Optional[str] = None,
        feature_columns: Optional[List[str]] = None,
    ) -> Optional[SandboxReport]:
        """
        Run sandbox validation against an existing contract.
        Useful for re-validation after the analysis pipeline has run.
        """
        try:
            modality_result = contract.modality_result
            routing_conf    = contract.routing_confidence
            if modality_result is None or routing_conf is None:
                return contract.sandbox_report
            ctx = {
                "target_available": target_available,
                "target_column": target_column,
                "feature_columns": feature_columns or [],
                "missing_rate_overall": float(df.isna().mean().mean()),
                "has_department_column": any(
                    "department" in c.lower() or "division" in c.lower()
                    for c in df.columns
                ),
                "has_temporal_column": contract.time_column is not None,
                "semantic_mapping": contract.semantic_map_v2,
            }
            return self._sandbox.validate_all(modality_result, routing_conf, df, ctx)
        except Exception as _e:
            logger.warning(f"validate_sandbox failed: {_e}")
            return None

    def describe(self, contract: DatasetContract) -> str:
        lines = [
            f"DatasetContract",
            f"  type           : {contract.dataset_type} ({contract.confidence:.0%})",
            f"  subtype        : {contract.dataset_subtype}",
            f"  row_unit       : {contract.row_unit}",
            f"  target         : {contract.target_column or 'none'} ({contract.target_available})",
            f"  is_biosignal   : {contract.is_biosignal}",
            f"  signal_type    : {contract.detected_signal_type or 'n/a'}",
            f"  quality        : {contract.quality_score:.0f}/100",
            f"  pipeline       : {contract.recommended_pipeline}",
            "",
            "  Compatible:"
        ]
        for a in contract.compatible_analyses:
            lines.append(f"    ✓ {a}")
        lines.append("  Blocked:")
        for a in contract.blocked_analyses[:6]:
            lines.append(f"    ✗ {a}")
        if contract.warning_messages:
            lines.append("  Warnings:")
            for w in contract.warning_messages:
                lines.append(f"    ⚠ {w[:100]}")
        return "\n".join(lines)
