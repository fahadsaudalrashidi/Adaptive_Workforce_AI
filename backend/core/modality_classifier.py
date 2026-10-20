"""
Modality Classifier
Universal dataset modality detection with multi-signal evidence scoring.

Modalities:
  TABULAR_HR         — employee records with HR schema
  TABULAR_SURVEY     — Likert-scale / psychological survey
  TABULAR_FINANCIAL  — financial transactions, compensation
  TABULAR_GENERIC    — structured tabular, unknown domain
  BIOSIGNAL          — physiological sensor time-series
  GENERIC_TIMESERIES — time-indexed sequential data, non-biosignal
  NLP_TEXT           — free-text, unstructured content
  MULTIMODAL         — mix of modalities
  UNKNOWN            — cannot classify with adequate confidence

Every result carries:
  confidence        — 0–1 overall classification certainty
  provenance        — evidence signals that drove the decision
  assumptions       — what was assumed, not observed
  caveats           — limitations of this classification
  validity_score    — reliability of the classification itself
"""
from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ── Modality enum ────────────────────────────────────────────────────────────

class Modality(str, Enum):
    TABULAR_HR         = "tabular_hr"
    TABULAR_SURVEY     = "tabular_survey"
    TABULAR_FINANCIAL  = "tabular_financial"
    TABULAR_GENERIC    = "tabular_generic"
    BIOSIGNAL          = "biosignal_timeseries"
    GENERIC_TIMESERIES = "generic_timeseries"
    NLP_TEXT           = "nlp_text"
    MULTIMODAL         = "multimodal"
    UNKNOWN            = "unknown"


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class EvidenceSignal:
    """A single piece of evidence contributing to modality classification."""
    signal_type: str       # "filename" / "column_name" / "value_dist" / "statistical" / "structural"
    description: str       # what was observed
    modality: str          # which modality this supports
    weight: float          # 0–1 contribution weight
    confidence: float      # 0–1 reliability of this signal


@dataclass
class ModalityResult:
    modality: Modality
    sub_modality: str           # e.g. "wesad_biosignal", "hr_attrition", "psychological_survey"
    confidence: float           # 0–1 overall confidence in the classification
    runner_up: Optional[Modality]  # second-best modality
    runner_up_confidence: float
    evidence: List[EvidenceSignal]
    provenance: List[str]       # human-readable evidence chain
    assumptions: List[str]      # what was assumed
    caveats: List[str]          # limitations
    validity_score: float       # reliability of the classification process itself
    signal_type_hint: Optional[str]  # e.g. "HR", "EDA", "BVP" for biosignal
    row_unit_hint: str          # suggested row unit
    n_rows: int
    n_cols: int
    numeric_col_pct: float
    high_freq_cols: List[str]   # columns with unusually high unique-value ratios


# ── Keyword tables ────────────────────────────────────────────────────────────

_BIOSIGNAL_FILENAME_STEMS = {
    "hr":   ("HR",   0.99),
    "eda":  ("EDA",  0.99),
    "bvp":  ("BVP",  0.99),
    "temp": ("TEMP", 0.99),
    "acc":  ("ACC",  0.99),
    "ibi":  ("IBI",  0.99),
    "ecg":  ("ECG",  0.95),
    "eeg":  ("EEG",  0.95),
    "ppg":  ("PPG",  0.95),
    "emg":  ("EMG",  0.90),
    "gsr":  ("GSR",  0.90),
    "signal":  ("SIGNAL", 0.80),
    "physio":  ("SIGNAL", 0.80),
    "wearable":("WEARABLE",0.80),
    "empatica":("E4", 0.85),
    "wesad":   ("WESAD",0.90),
}

_BIOSIGNAL_FILENAME_PATTERNS = [
    (r"wesad",        0.90),
    (r"empatica",     0.85),
    (r"e4_|_e4",      0.85),
    (r"_sensor",      0.75),
    (r"biometric",    0.75),
    (r"physio",       0.80),
    (r"galvanic",     0.90),
    (r"skin_cond",    0.90),
    (r"wearable",     0.80),
]

# Biosignal column keywords (strong signal)
_BIOSIGNAL_COL_KEYWORDS: List[Tuple[str, float]] = [
    ("eda",              0.95),
    ("bvp",              0.95),
    ("ibi",              0.95),
    ("hrv",              0.90),
    ("gsr",              0.90),
    ("ecg",              0.90),
    ("eeg",              0.90),
    ("emg",              0.90),
    ("galvanic",         0.90),
    ("skin_conductance", 0.90),
    ("blood_volume",     0.90),
    ("inter_beat",       0.90),
    ("rr_interval",      0.90),
    ("nn_interval",      0.90),
    ("ppg",              0.90),
    ("accelerometer",    0.75),
    ("heart_rate",       0.75),
    ("heartrate",        0.75),
    ("temperature",      0.60),  # ambiguous — also ambient temp
]

# HR / workforce keywords
_HR_COL_KEYWORDS: List[Tuple[str, float]] = [
    ("attrition",        1.00),
    ("employee",         0.90),
    ("turnover",         0.95),
    ("resignation",      0.90),
    ("department",       0.70),
    ("jobsatisfaction",  0.85),
    ("yearsatcompany",   0.90),
    ("monthlyincome",    0.90),
    ("salary",           0.70),
    ("jobrole",          0.80),
    ("joblevel",         0.80),
    ("performancerating",0.80),
    ("overtime",         0.70),
    ("businesstravel",   0.80),
    ("maritalstatus",    0.65),
    ("education",        0.50),
    ("gender",           0.50),  # also appears in surveys
    ("age",              0.40),  # very common, low weight
    ("hires",            0.75),
    ("headcount",        0.75),
    ("workforce",        0.80),
    ("hr_",              0.70),
    ("emp_",             0.70),
    ("staff_",           0.70),
]

# Survey keywords
_SURVEY_COL_KEYWORDS: List[Tuple[str, float]] = [
    ("burnout",          0.90),
    ("exhaustion",       0.85),
    ("engagement",       0.80),
    ("wellbeing",        0.80),
    ("stress",           0.75),
    ("satisfaction",     0.70),
    ("cynicism",         0.90),
    ("likert",           0.95),
    ("questionnaire",    0.90),
    ("survey",           0.80),
    ("scale_",           0.75),
    ("_score",           0.60),
    ("psycho",           0.80),
    ("mbi_",             0.95),   # Maslach Burnout Inventory
    ("q1_",              0.70),
    ("q2_",              0.70),
    ("item_",            0.75),
]

# Financial keywords
_FINANCIAL_COL_KEYWORDS: List[Tuple[str, float]] = [
    ("revenue",          0.90),
    ("profit",           0.90),
    ("transaction",      0.90),
    ("amount",           0.70),
    ("invoice",          0.90),
    ("payment",          0.85),
    ("balance",          0.80),
    ("debit",            0.90),
    ("credit",           0.90),
    ("cost",             0.65),
    ("price",            0.65),
    ("expense",          0.80),
    ("budget",           0.80),
    ("fiscal",           0.85),
    ("quarter",          0.75),
    ("financial",        0.85),
]

# Time-series structural indicators
_TIMESERIES_INDICATORS: List[Tuple[str, float]] = [
    ("timestamp",        0.90),
    ("datetime",         0.90),
    ("time",             0.70),
    ("date",             0.70),
    ("period",           0.65),
    ("week",             0.60),
    ("month",            0.60),
    ("year",             0.55),
    ("sequence",         0.65),
    ("step",             0.60),
    ("index",            0.50),
]


# ── Statistical feature extraction ───────────────────────────────────────────

def _col_stats(df: pd.DataFrame) -> Dict[str, Dict]:
    stats: Dict[str, Dict] = {}
    for col in df.columns:
        s = df[col].dropna()
        n = len(s)
        if n == 0:
            stats[col] = {"n": 0}
            continue
        n_unique = int(s.nunique())
        uniq_ratio = n_unique / max(n, 1)
        is_numeric = pd.api.types.is_numeric_dtype(s)

        d: Dict = {
            "n": n,
            "n_unique": n_unique,
            "uniq_ratio": uniq_ratio,
            "is_numeric": is_numeric,
            "is_datetime": False,
            "is_text": False,
            "is_binary": False,
            "is_likert": False,
            "max_str_len": 0,
        }

        if is_numeric:
            mn, mx = float(s.min()), float(s.max())
            d["min"] = mn
            d["max"] = mx
            d["std"] = float(s.std()) if n > 1 else 0.0
            d["mean"] = float(s.mean())
            # Likert detection: integer, range 1-7, few unique values
            if n_unique <= 7 and mn >= 1.0 and mx <= 7.0:
                try:
                    if (s == s.round()).all():
                        d["is_likert"] = True
                except Exception:
                    pass
            # Binary detection
            if n_unique == 2:
                d["is_binary"] = True
        else:
            sample = s.astype(str)
            d["max_str_len"] = int(sample.str.len().max())
            d["mean_str_len"] = float(sample.str.len().mean())
            if d["max_str_len"] > 50:
                d["is_text"] = True
            # Datetime detection
            if n_unique < n * 0.99 and n_unique > 1:
                try:
                    pd.to_datetime(s.head(20), errors="raise")
                    d["is_datetime"] = True
                except Exception:
                    pass

        stats[col] = d
    return stats


def _score_columns(df: pd.DataFrame, keyword_table: List[Tuple[str, float]]) -> float:
    """Return normalised score 0–1 for how many column names match the keyword table."""
    if not df.columns.tolist():
        return 0.0
    total_weight = 0.0
    for col in df.columns:
        cl = col.lower().replace(" ", "_").replace("-", "_")
        for kw, w in keyword_table:
            if kw in cl:
                total_weight += w
                break
    # Normalise by number of columns × max possible weight per column
    norm = total_weight / max(len(df.columns), 1)
    return round(min(1.0, norm), 4)


def _likert_fraction(col_stats: Dict[str, Dict]) -> float:
    """Fraction of numeric columns that look Likert-scale."""
    numeric = [v for v in col_stats.values() if v.get("is_numeric") and v.get("n", 0) > 0]
    if not numeric:
        return 0.0
    likert = [v for v in numeric if v.get("is_likert")]
    return len(likert) / max(len(numeric), 1)


def _has_datetime_index(df: pd.DataFrame, col_stats: Dict[str, Dict]) -> bool:
    """True if there is a datetime column or a monotonically increasing numeric index."""
    for col, st in col_stats.items():
        if st.get("is_datetime"):
            return True
    # Check if any numeric column is monotonically non-decreasing
    for col in df.select_dtypes(include=[np.number]).columns[:5]:
        s = df[col].dropna()
        if len(s) > 10 and s.is_monotonic_increasing:
            return True
    return False


def _high_freq_numeric(df: pd.DataFrame, col_stats: Dict[str, Dict]) -> bool:
    """True if numeric columns have many unique values relative to rows (suggests sensor data)."""
    num_cols = [c for c, st in col_stats.items() if st.get("is_numeric") and st.get("n", 0) > 50]
    if not num_cols:
        return False
    high_freq = [c for c in num_cols if col_stats[c].get("uniq_ratio", 0) > 0.80]
    return len(high_freq) >= max(1, len(num_cols) // 2)


def _text_dominant(col_stats: Dict[str, Dict]) -> float:
    """Fraction of columns with long text content."""
    total = [v for v in col_stats.values() if v.get("n", 0) > 0]
    if not total:
        return 0.0
    text = [v for v in total if v.get("is_text")]
    return len(text) / max(len(total), 1)


def _single_column_biosignal(df: pd.DataFrame, col_stats: Dict[str, Dict]) -> bool:
    """Single or very few numeric columns with >1000 rows and high unique ratio — likely raw signal."""
    num_cols = [c for c, st in col_stats.items() if st.get("is_numeric")]
    if len(num_cols) > 4:
        return False
    if len(df) < 500:
        return False
    high_uniq = all(col_stats[c].get("uniq_ratio", 0) > 0.70 for c in num_cols)
    return high_uniq and len(num_cols) >= 1


# ── Main classifier ───────────────────────────────────────────────────────────

class ModalityClassifier:
    """
    Classifies the modality of any uploaded dataset.
    Multi-signal voting — filename, column names, value distributions, structure.
    """

    def classify(
        self,
        df: pd.DataFrame,
        filename: str = "",
        raw_bytes: Optional[bytes] = None,
    ) -> ModalityResult:
        """
        Classify dataset modality. Returns ModalityResult with full evidence.
        """
        filename_lower = filename.lower().strip() if filename else ""
        stem = re.sub(r"\.[^.]+$", "", filename_lower).strip()

        evidence: List[EvidenceSignal] = []
        scores: Dict[str, float] = {m.value: 0.0 for m in Modality}
        assumptions: List[str] = []
        caveats: List[str] = []

        n_rows, n_cols = df.shape
        col_stats = _col_stats(df)
        numeric_cols = [c for c, st in col_stats.items() if st.get("is_numeric")]
        numeric_pct = len(numeric_cols) / max(n_cols, 1)

        high_freq_cols = [
            c for c in numeric_cols if col_stats[c].get("uniq_ratio", 0) > 0.85
        ]

        # ── Signal 1: Filename hard rules ─────────────────────────────────────
        signal_type_hint: Optional[str] = None
        for name_stem, (sig_type, conf) in _BIOSIGNAL_FILENAME_STEMS.items():
            if stem == name_stem:
                scores[Modality.BIOSIGNAL.value] += conf * 5.0
                signal_type_hint = sig_type
                evidence.append(EvidenceSignal(
                    signal_type="filename",
                    description=f"Filename '{filename}' matches biosignal stem '{name_stem}'",
                    modality=Modality.BIOSIGNAL.value,
                    weight=5.0,
                    confidence=conf,
                ))
                break

        for pattern, conf in _BIOSIGNAL_FILENAME_PATTERNS:
            if re.search(pattern, filename_lower):
                scores[Modality.BIOSIGNAL.value] += conf * 3.0
                evidence.append(EvidenceSignal(
                    signal_type="filename",
                    description=f"Filename matches biosignal pattern '{pattern}'",
                    modality=Modality.BIOSIGNAL.value,
                    weight=3.0,
                    confidence=conf,
                ))
                break

        # HR filename patterns
        for pat, conf in [
            (r"employee|attrition|hr_data|workforce|turnover|staff", 0.85),
            (r"ibm.*hr|saudi.*hr|hr.*dataset", 0.90),
        ]:
            if re.search(pat, filename_lower):
                scores[Modality.TABULAR_HR.value] += conf * 3.0
                evidence.append(EvidenceSignal(
                    signal_type="filename",
                    description=f"Filename matches HR pattern '{pat}'",
                    modality=Modality.TABULAR_HR.value,
                    weight=3.0,
                    confidence=conf,
                ))

        # Survey filename patterns
        for pat, conf in [(r"survey|questionnaire|burnout|mbi|stress_survey", 0.85)]:
            if re.search(pat, filename_lower):
                scores[Modality.TABULAR_SURVEY.value] += conf * 3.0
                evidence.append(EvidenceSignal(
                    signal_type="filename",
                    description=f"Filename matches survey pattern",
                    modality=Modality.TABULAR_SURVEY.value,
                    weight=3.0,
                    confidence=conf,
                ))

        # ── Signal 2: Column name keyword scoring ─────────────────────────────
        biosig_col_score = _score_columns(df, _BIOSIGNAL_COL_KEYWORDS)
        hr_col_score     = _score_columns(df, _HR_COL_KEYWORDS)
        survey_col_score = _score_columns(df, _SURVEY_COL_KEYWORDS)
        fin_col_score    = _score_columns(df, _FINANCIAL_COL_KEYWORDS)
        ts_col_score     = _score_columns(df, _TIMESERIES_INDICATORS)

        _add_col_evidence(evidence, scores, biosig_col_score, Modality.BIOSIGNAL.value, "biosignal column keywords", weight=4.0)
        _add_col_evidence(evidence, scores, hr_col_score,     Modality.TABULAR_HR.value,    "HR column keywords",      weight=3.0)
        _add_col_evidence(evidence, scores, survey_col_score, Modality.TABULAR_SURVEY.value, "survey column keywords", weight=3.0)
        _add_col_evidence(evidence, scores, fin_col_score,    Modality.TABULAR_FINANCIAL.value, "financial column keywords", weight=3.0)
        _add_col_evidence(evidence, scores, ts_col_score,     Modality.GENERIC_TIMESERIES.value, "time-series column keywords", weight=2.0)

        # ── Signal 3: Value distribution heuristics ───────────────────────────

        # Likert fraction → survey
        likert_frac = _likert_fraction(col_stats)
        if likert_frac > 0.40:
            w = likert_frac * 3.0
            scores[Modality.TABULAR_SURVEY.value] += w
            evidence.append(EvidenceSignal(
                signal_type="value_dist",
                description=f"{likert_frac:.0%} of numeric columns look Likert-scale (1–7)",
                modality=Modality.TABULAR_SURVEY.value,
                weight=w,
                confidence=likert_frac,
            ))

        # Single-column / few-column biosignal
        if _single_column_biosignal(df, col_stats):
            scores[Modality.BIOSIGNAL.value] += 3.5
            evidence.append(EvidenceSignal(
                signal_type="structural",
                description=f"1–4 columns, {n_rows:,} rows, high unique-value ratio — likely raw sensor data",
                modality=Modality.BIOSIGNAL.value,
                weight=3.5,
                confidence=0.80,
            ))

        # High-frequency numeric (sensor-like)
        if _high_freq_numeric(df, col_stats) and n_rows > 1000:
            w = 2.0
            scores[Modality.BIOSIGNAL.value] += w
            evidence.append(EvidenceSignal(
                signal_type="statistical",
                description=f">50% of numeric columns have >80% unique values — high-frequency sensor pattern",
                modality=Modality.BIOSIGNAL.value,
                weight=w,
                confidence=0.70,
            ))

        # Datetime index → timeseries
        if _has_datetime_index(df, col_stats):
            scores[Modality.GENERIC_TIMESERIES.value] += 2.0
            evidence.append(EvidenceSignal(
                signal_type="structural",
                description="Datetime column or monotonically increasing index detected",
                modality=Modality.GENERIC_TIMESERIES.value,
                weight=2.0,
                confidence=0.80,
            ))

        # Text-dominant → NLP
        txt_frac = _text_dominant(col_stats)
        if txt_frac > 0.50:
            w = txt_frac * 3.0
            scores[Modality.NLP_TEXT.value] += w
            evidence.append(EvidenceSignal(
                signal_type="value_dist",
                description=f"{txt_frac:.0%} of columns contain long text (>50 chars avg) — NLP candidate",
                modality=Modality.NLP_TEXT.value,
                weight=w,
                confidence=txt_frac,
            ))

        # ── Signal 4: Structural features ─────────────────────────────────────

        # Very few columns + numeric + many rows → sensor
        if n_cols <= 3 and n_rows > 2000 and numeric_pct >= 0.5:
            scores[Modality.BIOSIGNAL.value] += 2.0
            evidence.append(EvidenceSignal(
                signal_type="structural",
                description=f"Very few columns ({n_cols}) with many rows ({n_rows:,}) — sensor/timeseries structure",
                modality=Modality.BIOSIGNAL.value,
                weight=2.0,
                confidence=0.65,
            ))

        # Many binary columns → survey
        binary_cols = [c for c, st in col_stats.items() if st.get("is_binary") and st.get("is_numeric")]
        if len(binary_cols) >= 5 and len(binary_cols) / max(n_cols, 1) > 0.30:
            scores[Modality.TABULAR_SURVEY.value] += 1.5
            evidence.append(EvidenceSignal(
                signal_type="structural",
                description=f"{len(binary_cols)} binary flag columns — survey pattern",
                modality=Modality.TABULAR_SURVEY.value,
                weight=1.5,
                confidence=0.65,
            ))

        # Typical HR row count + column count
        if 50 <= n_rows <= 10000 and 10 <= n_cols <= 40 and hr_col_score > 0.10:
            scores[Modality.TABULAR_HR.value] += 1.5
            evidence.append(EvidenceSignal(
                signal_type="structural",
                description=f"Row/column dimensions ({n_rows}×{n_cols}) consistent with HR employee dataset",
                modality=Modality.TABULAR_HR.value,
                weight=1.5,
                confidence=0.60,
            ))

        # ── Resolve winner ────────────────────────────────────────────────────
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_key, top_score   = sorted_scores[0]
        sec_key, sec_score   = sorted_scores[1] if len(sorted_scores) > 1 else ("unknown", 0.0)
        total_score = sum(v for v in scores.values())

        if total_score == 0:
            raw_conf = 0.0
        else:
            raw_conf = top_score / total_score
            # Bonus: if top score is clearly dominant, raise confidence
            if top_score >= sec_score * 3.0:
                raw_conf = min(1.0, raw_conf * 1.20)

        # Confidence floor: if no strong evidence, cap at 0.50
        n_evidence_signals = len([e for e in evidence if e.weight >= 2.0])
        if n_evidence_signals == 0:
            raw_conf = min(raw_conf, 0.45)
            caveats.append("No strong evidence signals — classification is a weak heuristic guess.")
            assumptions.append("Dataset type inferred from column names and structure only.")

        confidence = round(min(1.0, max(0.0, raw_conf)), 4)
        runner_up_conf = round(sec_score / max(total_score, 1e-9), 4)

        # Map to Modality enum
        try:
            modality = Modality(top_key)
        except ValueError:
            modality = Modality.UNKNOWN

        # If confidence is below threshold, return UNKNOWN
        if confidence < 0.25:
            modality = Modality.UNKNOWN
            caveats.append(f"Classification confidence ({confidence:.0%}) below minimum threshold — returning UNKNOWN.")

        try:
            runner_up = Modality(sec_key)
        except ValueError:
            runner_up = None

        # Sub-modality
        sub_modality = _sub_modality(modality, signal_type_hint, hr_col_score, survey_col_score, filename_lower)

        # Row unit hint
        row_unit_hint = _row_unit_hint(modality)

        # Validity score: how trustworthy is the classification process
        validity_score = _compute_validity(confidence, n_evidence_signals, n_rows, n_cols)

        # Provenance strings
        provenance = [
            f"Modality: {modality.value} (confidence: {confidence:.0%})",
            f"Evidence signals: {len(evidence)} total",
            f"Runner-up: {runner_up.value if runner_up else 'none'} ({runner_up_conf:.0%})",
            f"Dataset shape: {n_rows:,} rows × {n_cols} columns",
            f"Numeric column fraction: {numeric_pct:.0%}",
            f"Validity score: {validity_score:.0%}",
        ]
        for ev in evidence[:5]:
            provenance.append(f"  [{ev.signal_type}] {ev.description} → {ev.modality}")

        # Biosignal-specific caveats
        if modality == Modality.BIOSIGNAL:
            caveats.append("Biosignal data: rows are sensor samples, NEVER employee records.")
            caveats.append("All HR/employee analytics are BLOCKED for this modality.")
        elif confidence < 0.60:
            caveats.append("Low classification confidence — verify dataset type before interpretation.")

        if not assumptions:
            assumptions.append("Column names are informative of their semantic meaning.")
            assumptions.append("Value distributions are representative of the full dataset.")

        return ModalityResult(
            modality=modality,
            sub_modality=sub_modality,
            confidence=confidence,
            runner_up=runner_up,
            runner_up_confidence=runner_up_conf,
            evidence=evidence,
            provenance=provenance,
            assumptions=assumptions,
            caveats=caveats,
            validity_score=validity_score,
            signal_type_hint=signal_type_hint,
            row_unit_hint=row_unit_hint,
            n_rows=n_rows,
            n_cols=n_cols,
            numeric_col_pct=numeric_pct,
            high_freq_cols=high_freq_cols[:10],
        )


# ── Private helpers ───────────────────────────────────────────────────────────

def _add_col_evidence(
    evidence: List[EvidenceSignal],
    scores: Dict[str, float],
    score: float,
    modality: str,
    label: str,
    weight: float,
) -> None:
    if score > 0.05:
        total_w = score * weight
        scores[modality] += total_w
        evidence.append(EvidenceSignal(
            signal_type="column_name",
            description=f"{label}: score={score:.2f}",
            modality=modality,
            weight=total_w,
            confidence=score,
        ))


def _sub_modality(
    modality: Modality,
    signal_type_hint: Optional[str],
    hr_score: float,
    survey_score: float,
    filename: str,
) -> str:
    if modality == Modality.BIOSIGNAL:
        if signal_type_hint:
            return f"wesad_{signal_type_hint.lower()}"
        return "physiological_sensor"
    if modality == Modality.TABULAR_HR:
        if "attrition" in filename or hr_score > 0.30:
            return "hr_attrition"
        return "hr_workforce"
    if modality == Modality.TABULAR_SURVEY:
        if "burnout" in filename or "mbi" in filename:
            return "burnout_survey"
        return "psychological_survey"
    if modality == Modality.TABULAR_FINANCIAL:
        return "financial_transactions"
    if modality == Modality.GENERIC_TIMESERIES:
        return "sequential_timeseries"
    if modality == Modality.NLP_TEXT:
        return "unstructured_text"
    if modality == Modality.MULTIMODAL:
        return "mixed_modality"
    return "unknown"


def _row_unit_hint(modality: Modality) -> str:
    mapping = {
        Modality.BIOSIGNAL:          "signal_samples",
        Modality.TABULAR_HR:         "employees",
        Modality.TABULAR_SURVEY:     "survey_responses",
        Modality.TABULAR_FINANCIAL:  "transactions",
        Modality.GENERIC_TIMESERIES: "time_windows",
        Modality.NLP_TEXT:           "documents",
        Modality.MULTIMODAL:         "records",
        Modality.TABULAR_GENERIC:    "records",
        Modality.UNKNOWN:            "records",
    }
    return mapping.get(modality, "records")


def _compute_validity(
    confidence: float,
    n_evidence: int,
    n_rows: int,
    n_cols: int,
) -> float:
    score = 1.0
    if confidence < 0.50:
        score *= 0.60
    elif confidence < 0.70:
        score *= 0.80
    if n_evidence == 0:
        score *= 0.50
    elif n_evidence == 1:
        score *= 0.75
    if n_rows < 10:
        score *= 0.50
    if n_cols < 2:
        score *= 0.70
    return round(min(1.0, max(0.0, score)), 4)
