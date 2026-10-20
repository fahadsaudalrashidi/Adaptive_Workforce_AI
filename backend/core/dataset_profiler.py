"""
Dataset Profiler — Universal Dataset Understanding Engine

Ingests any tabular file (CSV/XLSX/JSON/Parquet/PKL/Feather) and produces a
rich DatasetProfile: column types, semantic roles, quality scores, dataset-type
inference, and a readiness verdict for downstream ML.
"""
from __future__ import annotations

import io
import json
import logging
import pickle
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
logger = logging.getLogger(__name__)

# ── local imports ──────────────────────────────────────────────────────────
from config.settings import (
    SUPPORTED_EXTENSIONS,
    MAX_UPLOAD_MB,
    MAX_ROWS_PROFILE,
    MISSING_WARN_THRESHOLD,
    MISSING_DROP_THRESHOLD,
    CARDINALITY_HIGH,
    CARDINALITY_ID_LIKE,
    NUMERIC_SKEW_THRESHOLD,
    OUTLIER_IQR_FACTOR,
    MIN_ROWS_FOR_ML,
    DATASET_TYPES,
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColumnProfile:
    name: str
    dtype_raw: str
    inferred_type: str          # numeric / categorical / datetime / text / binary / id
    n_missing: int
    missing_rate: float
    n_unique: int
    unique_rate: float
    is_id_like: bool
    is_binary: bool
    is_high_cardinality: bool
    mean: Optional[float]       = None
    std: Optional[float]        = None
    min_val: Optional[float]    = None
    max_val: Optional[float]    = None
    median: Optional[float]     = None
    skewness: Optional[float]   = None
    kurtosis: Optional[float]   = None
    n_outliers: Optional[int]   = None
    top_values: Optional[List]  = None  # top-5 value_counts for categoricals
    sample_values: Optional[List] = None
    needs_log_transform: bool   = False
    needs_encoding: bool        = False


@dataclass
class DatasetProfile:
    # Identity
    source_path: str
    n_rows: int
    n_cols: int
    file_size_mb: float
    was_sampled: bool

    # Column profiles
    columns: Dict[str, ColumnProfile] = field(default_factory=dict)

    # Type breakdown
    numeric_cols: List[str]    = field(default_factory=list)
    categorical_cols: List[str] = field(default_factory=list)
    datetime_cols: List[str]   = field(default_factory=list)
    text_cols: List[str]       = field(default_factory=list)
    binary_cols: List[str]     = field(default_factory=list)
    id_cols: List[str]         = field(default_factory=list)

    # Quality
    overall_quality_score: float = 0.0   # 0–100
    quality_flags: List[str]     = field(default_factory=list)
    missing_summary: Dict[str, float] = field(default_factory=dict)
    columns_to_drop: List[str]   = field(default_factory=list)
    columns_to_warn: List[str]   = field(default_factory=list)

    # Dataset-type inference
    inferred_dataset_type: str   = "unknown"
    dataset_type_confidence: float = 0.0
    dataset_type_scores: Dict[str, float] = field(default_factory=dict)

    # Target detection
    candidate_targets: List[str] = field(default_factory=list)
    recommended_target: Optional[str] = None
    recommended_task: str        = "binary_classification"

    # Readiness
    ml_ready: bool               = False
    readiness_issues: List[str]  = field(default_factory=list)

    # Temporal structure
    has_temporal: bool           = False
    temporal_cols: List[str]     = field(default_factory=list)
    temporal_resolution: Optional[str] = None   # daily/monthly/yearly


# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD SIGNALS for dataset-type scoring
# ─────────────────────────────────────────────────────────────────────────────

_TYPE_SIGNALS: Dict[str, List[str]] = {
    "hr_attrition": [
        "attrition", "turnover", "left", "resigned", "quit", "churn", "exit",
        "voluntary", "involuntary", "terminated", "separated", "departure",
    ],
    "hr_engagement": [
        "engagement", "satisfaction", "morale", "commitment", "loyalty",
        "eNPS", "pulse", "survey", "feeling", "motivation", "wellbeing",
    ],
    "hr_performance": [
        "performance", "rating", "appraisal", "review", "kpi", "goal",
        "target", "achievement", "score", "OKR", "bonus", "incentive",
    ],
    "hr_recruitment": [
        "applicant", "candidate", "hire", "hired", "onboard", "recruiter",
        "interview", "offer", "sourced", "pipeline", "application",
    ],
    "burnout_survey": [
        "burnout", "exhaustion", "cynicism", "efficacy", "maslach", "MBI",
        "emotional", "depersonalization", "overload", "stress", "fatigue",
    ],
    "psychological_survey": [
        "likert", "scale", "construct", "anxiety", "depression", "wellbeing",
        "resilience", "coping", "support", "autonomy", "mastery",
    ],
    "time_series_hr": [
        "date", "month", "year", "quarter", "period", "timestamp", "week",
        "tenure", "longevity", "duration", "lag", "rolling",
    ],
    "biosignal": [
        "heart_rate", "hrv", "ecg", "eeg", "emg", "galvanic", "skin",
        "accelerometer", "gyroscope", "sensor", "wearable", "bpm", "hz",
    ],
    "productivity": [
        "tasks", "tickets", "commits", "output", "throughput", "velocity",
        "sprint", "productivity", "efficiency", "utilization",
    ],
    "compensation": [
        "salary", "wage", "pay", "compensation", "bonus", "equity",
        "stock", "benefit", "total_comp", "raise", "increment",
    ],
    "learning_development": [
        "training", "course", "certification", "skill", "learning",
        "development", "mentoring", "coaching", "education", "upskill",
    ],
    "workforce_planning": [
        "headcount", "FTE", "capacity", "forecast", "plan", "budget",
        "vacancy", "requisition", "workforce", "staffing",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# LOADER
# ─────────────────────────────────────────────────────────────────────────────

def load_dataframe(source: str | Path | bytes | io.BytesIO,
                   filename: str = "") -> Tuple[pd.DataFrame, str, float]:
    """
    Load any supported file format into a DataFrame.
    Returns (df, resolved_extension, file_size_mb).
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        ext  = path.suffix.lower()
        size = path.stat().st_size / (1024 ** 2)
        raw  = path.read_bytes()
    elif isinstance(source, (bytes, bytearray)):
        raw  = bytes(source)
        ext  = Path(filename).suffix.lower() if filename else ".csv"
        size = len(raw) / (1024 ** 2)
    elif isinstance(source, io.IOBase):
        raw  = source.read()
        ext  = Path(filename).suffix.lower() if filename else ".csv"
        size = len(raw) / (1024 ** 2)
    else:
        raise TypeError(f"Unsupported source type: {type(source)}")

    if size > MAX_UPLOAD_MB:
        raise ValueError(f"File too large: {size:.1f} MB > {MAX_UPLOAD_MB} MB limit")

    buf = io.BytesIO(raw)

    if ext in (".csv",):
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                buf.seek(0)
                df = pd.read_csv(buf, encoding=enc, low_memory=False)
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        else:
            raise ValueError("Could not decode CSV with any standard encoding")

    elif ext in (".xlsx", ".xls"):
        buf.seek(0)
        df = pd.read_excel(buf)

    elif ext == ".json":
        buf.seek(0)
        try:
            df = pd.read_json(buf)
        except ValueError:
            buf.seek(0)
            data = json.load(buf)
            df   = pd.json_normalize(data)

    elif ext == ".parquet":
        buf.seek(0)
        df = pd.read_parquet(buf)

    elif ext in (".pkl", ".pickle"):
        buf.seek(0)
        obj = pickle.load(buf)
        if isinstance(obj, pd.DataFrame):
            df = obj
        else:
            raise ValueError("Pickle file does not contain a DataFrame")

    elif ext == ".feather":
        buf.seek(0)
        df = pd.read_feather(buf)

    else:
        raise ValueError(f"Unsupported extension: {ext}. Supported: {SUPPORTED_EXTENSIONS}")

    df.columns = [str(c).strip() for c in df.columns]
    return df, ext, size


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN-LEVEL PROFILER
# ─────────────────────────────────────────────────────────────────────────────

def _infer_column_type(series: pd.Series) -> str:
    """Return: numeric / categorical / datetime / text / binary / id"""
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    non_null = series.dropna()
    if len(non_null) == 0:
        return "categorical"

    # try datetime parse if object dtype with plausible date strings
    if series.dtype == object:
        sample = non_null.head(30).astype(str)
        parsed = pd.to_datetime(sample, errors="coerce", infer_datetime_format=True)
        if parsed.notna().mean() > 0.80:
            return "datetime"

        # long free-text?
        avg_len = sample.str.len().mean()
        if avg_len > 60:
            return "text"

        return "categorical"

    if pd.api.types.is_numeric_dtype(series):
        uniq = non_null.nunique()
        if uniq == 2:
            return "binary"
        return "numeric"

    if pd.api.types.is_bool_dtype(series):
        return "binary"

    return "categorical"


def _profile_column(series: pd.Series) -> ColumnProfile:
    n        = len(series)
    n_miss   = int(series.isna().sum())
    n_unique = int(series.nunique(dropna=True))
    ur       = n_unique / max(n - n_miss, 1)
    ctype    = _infer_column_type(series)

    prof = ColumnProfile(
        name              = series.name,
        dtype_raw         = str(series.dtype),
        inferred_type     = ctype,
        n_missing         = n_miss,
        missing_rate      = n_miss / max(n, 1),
        n_unique          = n_unique,
        unique_rate       = ur,
        is_id_like        = ur > CARDINALITY_ID_LIKE,
        is_binary         = ctype == "binary",
        is_high_cardinality = (ctype == "categorical" and n_unique > CARDINALITY_HIGH),
        sample_values     = series.dropna().head(5).tolist(),
    )

    if ctype in ("numeric", "binary"):
        num = pd.to_numeric(series, errors="coerce").dropna()
        if len(num) > 0:
            prof.mean    = float(num.mean())
            prof.std     = float(num.std())
            prof.min_val = float(num.min())
            prof.max_val = float(num.max())
            prof.median  = float(num.median())
            prof.skewness = float(num.skew())
            prof.kurtosis = float(num.kurtosis())
            # outliers via IQR
            q1, q3 = num.quantile([0.25, 0.75])
            iqr    = q3 - q1
            lo, hi = q1 - OUTLIER_IQR_FACTOR * iqr, q3 + OUTLIER_IQR_FACTOR * iqr
            prof.n_outliers = int(((num < lo) | (num > hi)).sum())
            prof.needs_log_transform = (abs(prof.skewness) > NUMERIC_SKEW_THRESHOLD
                                         and prof.min_val >= 0)

    if ctype == "categorical":
        vc = series.value_counts(dropna=True)
        prof.top_values   = list(zip(vc.index[:5].tolist(), vc.values[:5].tolist()))
        prof.needs_encoding = True

    return prof


# ─────────────────────────────────────────────────────────────────────────────
# DATASET-TYPE SCORER
# ─────────────────────────────────────────────────────────────────────────────

def _score_dataset_types(df: pd.DataFrame) -> Dict[str, float]:
    """Score each dataset type 0–1 based on column-name keyword overlap."""
    all_text = " ".join(df.columns).lower()
    scores: Dict[str, float] = {}
    for dtype, keywords in _TYPE_SIGNALS.items():
        hits = sum(1 for kw in keywords if kw.lower() in all_text)
        scores[dtype] = min(1.0, hits / max(len(keywords) * 0.30, 1))
    # normalise
    total = sum(scores.values()) or 1.0
    return {k: round(v / total, 4) for k, v in scores.items()}


def _infer_dataset_type(scores: Dict[str, float]) -> Tuple[str, float]:
    best = max(scores, key=scores.get)
    conf = scores[best]
    # If top score too low → mixed/unknown
    if conf < 0.08:
        return "unknown", conf
    # If top-2 close → mixed
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and (sorted_scores[0] - sorted_scores[1]) < 0.04:
        return "mixed", conf
    return best, conf


# ─────────────────────────────────────────────────────────────────────────────
# TARGET DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_TARGET_KEYWORDS = [
    "attrition", "turnover", "churn", "left", "resigned", "exit", "outcome",
    "target", "label", "class", "y", "result", "status", "event",
    "hired", "promoted", "fired", "terminated", "separated",
]


def _detect_target_columns(df: pd.DataFrame) -> Tuple[List[str], Optional[str], str]:
    """Returns (candidates, recommended, recommended_task)."""
    candidates: List[str] = []
    col_lower = {c.lower(): c for c in df.columns}

    for kw in _TARGET_KEYWORDS:
        for lc, orig in col_lower.items():
            if kw in lc and orig not in candidates:
                candidates.append(orig)

    # Score: prefer binary columns that look like labels
    ranked: List[Tuple[str, float]] = []
    for col in candidates:
        s   = df[col].dropna()
        n_u = s.nunique()
        score = 0.0
        # binary → best
        if n_u == 2:
            score += 1.0
        elif n_u <= 5:
            score += 0.5
        # keyword match weight
        for kw in _TARGET_KEYWORDS[:6]:  # top keywords matter more
            if kw in col.lower():
                score += 0.3
        ranked.append((col, score))

    ranked.sort(key=lambda x: x[1], reverse=True)
    recommended = ranked[0][0] if ranked else None

    task = "binary_classification"
    if recommended:
        s = df[recommended].dropna()
        n_u = s.nunique()
        if n_u == 2:
            task = "binary_classification"
        elif 2 < n_u <= 15:
            task = "multiclass_classification"
        elif pd.api.types.is_numeric_dtype(s) and n_u > 15:
            task = "regression"

    return candidates, recommended, task


# ─────────────────────────────────────────────────────────────────────────────
# TEMPORAL STRUCTURE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_DATE_KEYWORDS = [
    "date", "time", "timestamp", "month", "year", "quarter", "period",
    "created", "updated", "joined", "hired_date", "start_date", "end_date",
]


def _detect_temporal(df: pd.DataFrame,
                     col_profiles: Dict[str, ColumnProfile]) -> Tuple[bool, List[str], Optional[str]]:
    temporal = []
    for col, p in col_profiles.items():
        if p.inferred_type == "datetime":
            temporal.append(col)
        elif any(kw in col.lower() for kw in _DATE_KEYWORDS):
            temporal.append(col)

    if not temporal:
        return False, [], None

    # infer resolution from first temporal col
    resolution = None
    for col in temporal:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
            parsed = parsed.dropna().sort_values()
            if len(parsed) > 2:
                diffs = parsed.diff().dropna()
                med   = diffs.median()
                days  = med.days if hasattr(med, "days") else 0
                if days <= 1:
                    resolution = "daily"
                elif days <= 8:
                    resolution = "weekly"
                elif days <= 35:
                    resolution = "monthly"
                elif days <= 100:
                    resolution = "quarterly"
                else:
                    resolution = "yearly"
                break
        except Exception:
            continue

    return True, temporal, resolution


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY SCORING
# ─────────────────────────────────────────────────────────────────────────────

def _compute_quality(df: pd.DataFrame,
                     col_profiles: Dict[str, ColumnProfile]) -> Tuple[float, List[str], List[str], List[str]]:
    """
    Returns (score 0–100, quality_flags, columns_to_drop, columns_to_warn).
    Deductions: missing data, duplicate rows, high-cardinality IDs, all-same cols.
    """
    flags: List[str] = []
    drop: List[str]  = []
    warn: List[str]  = []
    score = 100.0

    # 1. Row count
    if len(df) < MIN_ROWS_FOR_ML:
        flags.append(f"Too few rows ({len(df)}) — ML requires ≥{MIN_ROWS_FOR_ML}")
        score -= 30

    # 2. Duplicate rows
    dup_rate = df.duplicated().mean()
    if dup_rate > 0.05:
        flags.append(f"High duplicate row rate: {dup_rate:.1%}")
        score -= min(15, dup_rate * 100)

    # 3. Per-column quality
    for col, p in col_profiles.items():
        if p.missing_rate >= MISSING_DROP_THRESHOLD:
            drop.append(col)
            flags.append(f"'{col}': {p.missing_rate:.0%} missing → will drop")
            score -= 3
        elif p.missing_rate >= MISSING_WARN_THRESHOLD:
            warn.append(col)
            score -= 1

        if p.is_id_like and p.inferred_type not in ("datetime",):
            flags.append(f"'{col}': likely ID column (unique rate {p.unique_rate:.0%})")

        if p.n_unique == 1:
            drop.append(col)
            flags.append(f"'{col}': constant — will drop")
            score -= 2

    score = max(0.0, min(100.0, score))
    return score, flags, list(set(drop)), list(set(warn))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PROFILER
# ─────────────────────────────────────────────────────────────────────────────

class DatasetProfiler:
    """
    Universal dataset profiler. Call `.profile(source)` to get a DatasetProfile.
    """

    def profile(self,
                source: str | Path | bytes | io.BytesIO,
                filename: str = "") -> DatasetProfile:
        df, ext, size_mb = load_dataframe(source, filename)
        logger.info("Loaded %d×%d DataFrame (%.2f MB)", len(df), len(df.columns), size_mb)

        # Optional: sample for very large datasets
        was_sampled = False
        if len(df) > MAX_ROWS_PROFILE:
            df = df.sample(MAX_ROWS_PROFILE, random_state=42).reset_index(drop=True)
            was_sampled = True
            logger.info("Sampled down to %d rows", MAX_ROWS_PROFILE)

        # ── column profiles ──────────────────────────────────────────────
        col_profiles: Dict[str, ColumnProfile] = {}
        for col in df.columns:
            col_profiles[col] = _profile_column(df[col].rename(col))

        # ── type groupings ───────────────────────────────────────────────
        numeric_cols    = [c for c, p in col_profiles.items() if p.inferred_type == "numeric"]
        categorical_cols = [c for c, p in col_profiles.items() if p.inferred_type == "categorical"]
        datetime_cols   = [c for c, p in col_profiles.items() if p.inferred_type == "datetime"]
        text_cols       = [c for c, p in col_profiles.items() if p.inferred_type == "text"]
        binary_cols     = [c for c, p in col_profiles.items() if p.inferred_type == "binary"]
        id_cols         = [c for c, p in col_profiles.items() if p.is_id_like]

        missing_summary = {c: round(p.missing_rate, 4)
                           for c, p in col_profiles.items() if p.missing_rate > 0}

        # ── quality ──────────────────────────────────────────────────────
        q_score, q_flags, drop_cols, warn_cols = _compute_quality(df, col_profiles)

        # ── dataset-type inference ────────────────────────────────────────
        type_scores                    = _score_dataset_types(df)
        inferred_type, type_confidence = _infer_dataset_type(type_scores)

        # ── target detection ─────────────────────────────────────────────
        candidates, rec_target, rec_task = _detect_target_columns(df)

        # ── temporal ─────────────────────────────────────────────────────
        has_temporal, temporal_cols, ts_res = _detect_temporal(df, col_profiles)
        if has_temporal and inferred_type == "unknown":
            inferred_type = "time_series_hr"

        # ── ML readiness ─────────────────────────────────────────────────
        readiness_issues: List[str] = []
        if len(df) < MIN_ROWS_FOR_ML:
            readiness_issues.append(f"Insufficient rows ({len(df)} < {MIN_ROWS_FOR_ML})")
        if rec_target is None:
            readiness_issues.append("No target column detected — manual selection required")
        if len(numeric_cols) + len(binary_cols) + len(categorical_cols) < 2:
            readiness_issues.append("Fewer than 2 usable feature columns")
        ml_ready = (len(readiness_issues) == 0)

        prof = DatasetProfile(
            source_path          = str(source) if isinstance(source, (str, Path)) else filename,
            n_rows               = len(df),
            n_cols               = len(df.columns),
            file_size_mb         = size_mb,
            was_sampled          = was_sampled,
            columns              = col_profiles,
            numeric_cols         = numeric_cols,
            categorical_cols     = categorical_cols,
            datetime_cols        = datetime_cols,
            text_cols            = text_cols,
            binary_cols          = binary_cols,
            id_cols              = id_cols,
            overall_quality_score = q_score,
            quality_flags        = q_flags,
            missing_summary      = missing_summary,
            columns_to_drop      = drop_cols,
            columns_to_warn      = warn_cols,
            inferred_dataset_type = inferred_type,
            dataset_type_confidence = type_confidence,
            dataset_type_scores  = type_scores,
            candidate_targets    = candidates,
            recommended_target   = rec_target,
            recommended_task     = rec_task,
            ml_ready             = ml_ready,
            readiness_issues     = readiness_issues,
            has_temporal         = has_temporal,
            temporal_cols        = temporal_cols,
            temporal_resolution  = ts_res,
        )

        logger.info(
            "Profile complete — type=%s (conf=%.2f), quality=%.0f/100, ml_ready=%s",
            inferred_type, type_confidence, q_score, ml_ready,
        )
        return prof

    def profile_to_dict(self, prof: DatasetProfile) -> Dict[str, Any]:
        """Serialize profile to a JSON-safe dict (for API responses)."""
        d = {k: v for k, v in prof.__dict__.items() if k != "columns"}
        d["columns"] = {
            col: {k: v for k, v in cp.__dict__.items()}
            for col, cp in prof.columns.items()
        }
        return d
