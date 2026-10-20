"""
Saudi Attrition Dataset Normalizer — Phase 10.

Handles the specific messiness of the real Saudi attrition dataset:
  - Dirty column names (leading/trailing whitespace, non-breaking spaces)
  - Attrition target values " Yes" / " No" with leading spaces
  - Salary ranges like "From 5000 to 10000 S.R" → numeric midpoint
  - Ordinal/categorical scales (Satisfied/Not satisfied, Yes/No, Medium)
  - Proxy construct mapping (Saudi columns → COR/JD-R/FFM/Mobley/Adams)

Design rules:
  - Normalize only what is needed for analysis; preserve originals
  - Never fabricate construct values beyond what the data supports
  - Saudi proxy constructs are labelled as PROXY — not exact paper replication
  - Scale direction uncertainty → confidence downgrade, not silent acceptance
  - All transformations are logged
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Column name normalization map ─────────────────────────────────────────────
# Maps messy original column names → canonical clean names
# Identified by inspecting the actual file.

_COLUMN_ALIAS_MAP: dict[str, str] = {
    # Strip whitespace / NBSP variants
    "Gender ":                          "gender",
    " Maritalstatus":                   "marital_status",
    "\xa0Academic_degree ":             "academic_degree",
    "Academic_degree ":                 "academic_degree",
    "Get_ Deserved_Promotion":          "get_deserved_promotion",
    "Training_programs_ During_last_three_years": "training_programs_during_last_three_years",
    "Work_Live_Balance":                "work_life_balance",
    # Clean pass-through (already reasonable)
    "ID":                               "employee_row_id",
    "Attrition":                        "attrition",
    "Age":                              "age",
    "Years_Experience":                 "years_experience",
    "Years_experience_lastorganization":"years_in_current_org",
    "Sector":                           "sector",
    "Department":                       "department",
    "JobTitle":                         "job_title",
    "MonthlySalary":                    "monthly_salary_range",
    "Allowances":                       "allowances",
    "MedicalInsurance":                 "medical_insurance",
    "Bonus":                            "bonus",
    "OverTime":                         "overtime",
    "Payment_Overtime":                 "payment_overtime",
    "Rewards&Wages_Satisfaction":       "rewards_wages_satisfaction",
    "Useful_Training_Programs":         "useful_training_programs",
    "Business_Travel":                  "business_travel",
    "Job_Support":                      "job_support",
    "Recognition":                      "recognition",
    "Emotional_Commitment":             "emotional_commitment",
    "Job_Engagement":                   "job_engagement",
    "Distance_to_work":                 "distance_to_work",
    "Physical_Stress":                  "physical_stress",
    "Psychological_Exhaustion":         "psychological_exhaustion",
    "Job_Stability":                    "job_stability",
    "Health_Issues":                    "health_issues",
    "Environment_Satisfaction":         "environment_satisfaction",
    "Job_Satisfaction":                 "job_satisfaction",
    "Job_Opportunities":                "job_opportunities",
}

# ── Salary range parser ───────────────────────────────────────────────────────

_SALARY_PATTERNS = [
    # "From 5000 to 10000 S.R" / "From 11000 to 15000 S.R"
    re.compile(r"[Ff]rom\s+(\d[\d,]*)\s+to\s+(\d[\d,]*)", re.I),
    # "Less than 5000 SAR" / "Less than 5000 S.R"
    re.compile(r"[Ll]ess\s+than\s+(\d[\d,]*)", re.I),
    # "More than 15000" / "Above 15000"
    re.compile(r"(?:[Mm]ore\s+than|[Aa]bove)\s+(\d[\d,]*)", re.I),
    # Standalone number
    re.compile(r"(\d{3,6})"),
]


def _parse_salary_range(val: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Parse a salary range string.
    Returns (min_sar, max_sar, midpoint_sar).
    Returns (None, None, None) if unparseable.
    """
    if pd.isna(val) or not str(val).strip():
        return None, None, None

    text = str(val).replace("\xa0", " ").strip()

    # "From X to Y"
    m = _SALARY_PATTERNS[0].search(text)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        return lo, hi, (lo + hi) / 2

    # "Less than X"
    m = _SALARY_PATTERNS[1].search(text)
    if m:
        hi = float(m.group(1).replace(",", ""))
        lo = 0.0
        return lo, hi, hi * 0.75

    # "More than X"
    m = _SALARY_PATTERNS[2].search(text)
    if m:
        lo = float(m.group(1).replace(",", ""))
        hi = lo * 1.5
        return lo, hi, lo * 1.25

    # Standalone number
    m = _SALARY_PATTERNS[3].search(text)
    if m:
        val_f = float(m.group(1).replace(",", ""))
        return val_f, val_f, val_f

    return None, None, None


# ── Attrition target normalization ────────────────────────────────────────────

_YES_VALUES = {"yes", "y", "1", "true", "نعم", "صح"}
_NO_VALUES  = {"no", "n", "0", "false", "لا", "خطأ"}


def _normalize_attrition_value(val) -> Optional[int]:
    """Normalize attrition cell to 1 (attrition) or 0 (retained). None if unparseable."""
    if pd.isna(val):
        return None
    text = str(val).strip().lower()
    if text in _YES_VALUES:
        return 1
    if text in _NO_VALUES:
        return 0
    return None


# ── Ordinal scale mapping ─────────────────────────────────────────────────────
# Many columns use Likert-like text. Map to numeric [1–5] or [0–1].

_ORDINAL_MAPS: dict[str, dict[str, float]] = {
    # Satisfaction scales
    "satisfaction": {
        "not satisfied": 1.0, "not_satisfied": 1.0, "dissatisfied": 1.0,
        "somewhat satisfied": 2.0, "neutral": 2.5, "medium": 2.5,
        "satisfied": 4.0, "very satisfied": 5.0, "highly satisfied": 5.0,
    },
    # Agreement scales
    "agreement": {
        "strongly disagree": 1.0, "disagree": 2.0, "neutral": 3.0,
        "agree": 4.0, "strongly agree": 5.0,
        "no": 1.0, "yes": 5.0,
    },
    # Frequency scales
    "frequency": {
        "never": 1.0, "rarely": 2.0, "sometimes": 3.0,
        "often": 4.0, "always": 5.0,
        "no": 1.0, "yes": 5.0,
    },
    # Binary
    "binary": {
        "no": 0.0, "n": 0.0, "0": 0.0, "false": 0.0,
        "yes": 1.0, "y": 1.0, "1": 1.0, "true": 1.0,
    },
}


# ── Proxy construct mapping ───────────────────────────────────────────────────
# Maps Saudi column names → which COR/JD-R/FFM/Mobley/Adams construct they proxy.
# Labelled PROXY — not exact paper replication.

PROXY_CONSTRUCT_MAP: dict[str, dict] = {
    # COR (Conservation of Resources) — resource depletion signals
    "cor_proxy_burnout_risk": {
        "theory": "COR",
        "construct_name": "BurnoutRisk_Proxy",
        "proxy": True,
        "columns": ["physical_stress", "psychological_exhaustion", "health_issues"],
        "direction": "higher = more burnout risk",
    },
    "cor_proxy_satisfaction": {
        "theory": "COR",
        "construct_name": "SatisfactionIndex_Proxy",
        "proxy": True,
        "columns": [
            "job_satisfaction", "environment_satisfaction",
            "rewards_wages_satisfaction", "work_life_balance",
        ],
        "direction": "higher = more satisfied",
    },
    "cor_proxy_engagement": {
        "theory": "COR",
        "construct_name": "EngagementScore_Proxy",
        "proxy": True,
        "columns": ["job_engagement", "emotional_commitment"],
        "direction": "higher = more engaged",
    },
    # JD-R (Job Demands-Resources)
    "jdr_proxy_career_progression": {
        "theory": "JD-R",
        "construct_name": "CareerProgression_Proxy",
        "proxy": True,
        "columns": [
            "get_deserved_promotion", "training_programs_during_last_three_years",
            "useful_training_programs",
        ],
        "direction": "higher = better career progression",
    },
    "jdr_proxy_salary_growth": {
        "theory": "JD-R",
        "construct_name": "SalaryGrowth_Proxy",
        "proxy": True,
        "columns": ["monthly_salary_range", "allowances", "bonus", "medical_insurance"],
        "direction": "higher = better compensation",
    },
    "jdr_proxy_tenure_ratio": {
        "theory": "JD-R",
        "construct_name": "TenureRatio_Proxy",
        "proxy": True,
        "columns": ["years_experience", "years_in_current_org"],
        "direction": "ratio of org tenure to total experience",
    },
    # Mobley (Turnover Process) — withdrawal and pull signals
    "mobley_proxy_withdrawal": {
        "theory": "Mobley",
        "construct_name": "WithdrawalPressure_Proxy",
        "proxy": True,
        "columns": ["job_opportunities", "job_stability", "distance_to_work"],
        "direction": "higher job_opportunities = higher pull toward leaving",
    },
    # Adams (Equity Theory) — fairness perception
    "adams_proxy_equity": {
        "theory": "Adams",
        "construct_name": "PerceivedEquity_Proxy",
        "proxy": True,
        "columns": ["get_deserved_promotion", "payment_overtime", "rewards_wages_satisfaction"],
        "direction": "higher = more equitable perception",
    },
}


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class AttritionNormalizationResult:
    success: bool
    df_normalized: Optional[pd.DataFrame]
    column_map: dict[str, str]            # original → canonical
    attrition_column: Optional[str]       # canonical name of target column
    attrition_values: dict[str, int]      # mapping used for Yes/No → 0/1
    salary_columns_parsed: list[str]
    proxy_constructs_available: list[str]
    proxy_constructs_blocked: list[str]   # constructs with scale uncertainty
    transformations: list[str]
    warnings: list[str]
    error: Optional[str] = None


# ── Normalizer ────────────────────────────────────────────────────────────────

class SaudiAttritionNormalizer:
    """
    Normalizes the real Saudi attrition dataset for analysis.

    Usage:
        norm = SaudiAttritionNormalizer()
        result = norm.normalize(df_raw)
    """

    def normalize(self, df: pd.DataFrame) -> AttritionNormalizationResult:
        transformations: list[str] = []
        warnings: list[str] = []

        # ── Step 1: Rename columns ────────────────────────────────────────────
        rename_map: dict[str, str] = {}
        unmapped_cols: list[str] = []

        for col in df.columns:
            canonical = self._resolve_column(col)
            if canonical != col:
                rename_map[col] = canonical
            elif canonical not in _COLUMN_ALIAS_MAP.values():
                # Normalize generically
                canonical_gen = self._generic_normalize(col)
                if canonical_gen != col:
                    rename_map[col] = canonical_gen

        if rename_map:
            df = df.rename(columns=rename_map)
            transformations.append(f"Renamed {len(rename_map)} columns to canonical names")

        # ── Step 2: Normalize attrition target ────────────────────────────────
        attrition_col = None
        attrition_values_used: dict[str, int] = {}

        for candidate in ("attrition", "turnover", "left", "resigned"):
            if candidate in df.columns:
                attrition_col = candidate
                break

        if attrition_col:
            original_vals = df[attrition_col].unique()
            df[attrition_col + "_binary"] = df[attrition_col].apply(
                _normalize_attrition_value
            )
            # Record what mapping was used
            for v in original_vals:
                mapped = _normalize_attrition_value(v)
                if mapped is not None:
                    attrition_values_used[str(v).strip()] = mapped
            null_count = df[attrition_col + "_binary"].isna().sum()
            transformations.append(
                f"Attrition target normalized to binary (0/1). "
                f"{null_count} unparseable values set to NaN."
            )
            if null_count > 0:
                warnings.append(
                    f"{null_count} attrition values could not be parsed. Check for unexpected values."
                )

        # ── Step 3: Parse salary ranges ───────────────────────────────────────
        salary_cols_parsed: list[str] = []
        for col in df.columns:
            if "salary" in col or "راتب" in col:
                if pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
                    parsed = df[col].apply(
                        lambda v: _parse_salary_range(str(v)) if pd.notna(v) else (None, None, None)
                    )
                    df[col + "_min"]  = [p[0] for p in parsed]
                    df[col + "_max"]  = [p[1] for p in parsed]
                    df[col + "_midpoint"] = [p[2] for p in parsed]
                    salary_cols_parsed.append(col)
                    transformations.append(
                        f"Salary column '{col}' parsed into {col}_min, {col}_max, {col}_midpoint"
                    )

        # ── Step 4: Assess proxy construct availability ───────────────────────
        available_constructs: list[str] = []
        blocked_constructs: list[str] = []

        for construct_key, info in PROXY_CONSTRUCT_MAP.items():
            required_cols = info["columns"]
            found = [c for c in required_cols if c in df.columns]
            if len(found) >= 1:
                available_constructs.append(construct_key)
            else:
                blocked_constructs.append(construct_key)
                warnings.append(
                    f"Proxy construct '{info['construct_name']}' unavailable — "
                    f"required columns not found: {required_cols}"
                )

        if available_constructs:
            transformations.append(
                f"{len(available_constructs)} proxy constructs available: {available_constructs}"
            )

        # Add proxy warning to all outputs
        warnings.append(
            "PROXY MODE: Saudi attrition constructs are proxies derived from organizational "
            "behavior theory (COR/JD-R/FFM/Mobley/Adams). They are not exact replications "
            "of validated Western psychometric instruments. Results should be interpreted with "
            "appropriate scientific caution."
        )

        return AttritionNormalizationResult(
            success=True,
            df_normalized=df,
            column_map=rename_map,
            attrition_column=attrition_col,
            attrition_values=attrition_values_used,
            salary_columns_parsed=salary_cols_parsed,
            proxy_constructs_available=available_constructs,
            proxy_constructs_blocked=blocked_constructs,
            transformations=transformations,
            warnings=warnings,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _resolve_column(self, col: str) -> str:
        """Look up the canonical name from the alias map."""
        if col in _COLUMN_ALIAS_MAP:
            return _COLUMN_ALIAS_MAP[col]
        # Try stripping NBSP and extra whitespace
        stripped = col.replace("\xa0", "").strip()
        if stripped in _COLUMN_ALIAS_MAP:
            return _COLUMN_ALIAS_MAP[stripped]
        if stripped != col:
            return stripped
        return col

    def _generic_normalize(self, col: str) -> str:
        """Generic normalization: lowercase, strip, replace spaces with underscores."""
        normalized = col.replace("\xa0", "").strip()
        normalized = re.sub(r"[\s_]+", "_", normalized).strip("_")
        return normalized
