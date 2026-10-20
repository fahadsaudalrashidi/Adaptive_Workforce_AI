"""
Data Healer — Self-Healing Data Pipeline

Receives a raw DataFrame + SemanticMap and produces a clean, ML-ready
DataFrame through a deterministic repair sequence:

  1. Drop junk columns (IDs, constants, >60% missing)
  2. Parse & standardise datetime columns
  3. Encode target labels → 0/1
  4. Repair numeric types (coerce, fix thousands-separator, strip currency)
  5. Handle missing values adaptively (median / mode / sentinel)
  6. Cap extreme outliers (IQR 3×)
  7. Log-transform high-skew numeric columns
  8. Encode categoricals (ordinal if ordered, one-hot if low-cardinality)
  9. Scale numeric features (StandardScaler or RobustScaler)
 10. Build HealReport with full audit trail

All transforms are recorded in HealReport.steps so they can be replayed on
new inference data via `DataHealer.transform_new(df_new)`.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, RobustScaler, StandardScaler

logger = logging.getLogger(__name__)

from config.settings import (
    MISSING_DROP_THRESHOLD,
    MISSING_WARN_THRESHOLD,
    CARDINALITY_HIGH,
    NUMERIC_SKEW_THRESHOLD,
    OUTLIER_IQR_FACTOR,
)
from .semantic_mapper import SemanticMap

# ─────────────────────────────────────────────────────────────────────────────
# ORDINAL KNOWLEDGE BASE
# ─────────────────────────────────────────────────────────────────────────────

_ORDINAL_MAPS: Dict[str, List[str]] = {
    # Education
    "education": ["below college", "college", "bachelor", "master", "doctor", "phd"],
    "education_level": ["high school", "diploma", "bachelor", "master", "phd", "doctorate"],
    # Performance / satisfaction
    "performance_rating": ["1", "2", "3", "4", "5"],
    "job_satisfaction": ["1", "2", "3", "4"],
    "environment_satisfaction": ["1", "2", "3", "4"],
    "relationship_satisfaction": ["1", "2", "3", "4"],
    "work_life_balance": ["1", "2", "3", "4"],
    # Job level
    "job_level": ["1", "2", "3", "4", "5"],
    # Generic Likert
    "likert_5": ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"],
    "likert_5b": ["never", "rarely", "sometimes", "often", "always"],
    "likert_7": ["1", "2", "3", "4", "5", "6", "7"],
}

_TARGET_POSITIVE = {
    "yes", "y", "1", "true", "t", "left", "resigned", "churned",
    "terminated", "separated", "attrited", "exit",
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealStep:
    step_name: str
    columns_affected: List[str]
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealReport:
    original_shape: Tuple[int, int]
    final_shape: Tuple[int, int]
    steps: List[HealStep] = field(default_factory=list)
    dropped_columns: List[str] = field(default_factory=list)
    encoded_columns: Dict[str, str] = field(default_factory=dict)   # col → method
    scaled_columns: List[str] = field(default_factory=list)
    imputed_columns: Dict[str, Any] = field(default_factory=dict)   # col → fill value
    log_transformed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    target_encoding: Optional[Dict[str, int]] = None
    feature_names_out: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _strip_currency(s: pd.Series) -> pd.Series:
    """Remove currency symbols and thousands separators from object series."""
    return (s.astype(str)
             .str.replace(r"[$€£¥,\s]", "", regex=True)
             .str.replace(r"[^\d.\-]", "", regex=True))


def _safe_to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    cleaned = _strip_currency(series)
    return pd.to_numeric(cleaned, errors="coerce")


def _detect_ordinal(series: pd.Series) -> Optional[List[str]]:
    """Return ordinal order if series looks like a known ordinal column, else None."""
    vals_lower = set(str(v).lower().strip() for v in series.dropna().unique())
    for order in _ORDINAL_MAPS.values():
        order_lower = [o.lower() for o in order]
        if vals_lower.issubset(set(order_lower)):
            return order_lower
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN HEALER
# ─────────────────────────────────────────────────────────────────────────────

class DataHealer:
    """
    Stateful healer: fit on training data, replay transforms on new data.

    Usage
    -----
    healer = DataHealer()
    df_clean, report = healer.fit_transform(df_raw, sem_map, target_col="Attrition")
    df_new_clean     = healer.transform_new(df_new)
    """

    def __init__(self, scaler_type: str = "robust"):
        self._scaler_type = scaler_type   # "robust" or "standard"
        self._report: Optional[HealReport] = None
        self._scaler: Optional[Any]        = None
        self._label_enc: Dict[str, LabelEncoder] = {}
        self._ordinal_enc: Dict[str, OrdinalEncoder] = {}
        self._ohe_cols: List[str] = []
        self._ohe_categories: Dict[str, List[str]] = {}
        self._log_cols: List[str] = []
        self._impute_values: Dict[str, Any] = {}
        self._scale_cols: List[str] = []
        self._target_col: Optional[str] = None
        self._target_map: Optional[Dict[str, int]] = None
        self._drop_cols: List[str] = []
        self._feature_names_out: List[str] = []

    # ── public API ──────────────────────────────────────────────────────────

    def fit_transform(self,
                      df: pd.DataFrame,
                      sem_map: SemanticMap,
                      target_col: Optional[str] = None) -> Tuple[pd.DataFrame, HealReport]:
        df = df.copy()
        report = HealReport(
            original_shape = df.shape,
            final_shape    = (0, 0),
        )
        self._report = report
        self._target_col = target_col or sem_map.target_col

        # 1. Drop junk
        df, report = self._step_drop_junk(df, sem_map, report)

        # 2. Parse datetimes (convert to numeric features)
        df, report = self._step_parse_datetimes(df, sem_map, report)

        # 3. Encode target
        df, report = self._step_encode_target(df, report)

        # 4. Coerce numerics
        df, report = self._step_coerce_numerics(df, report)

        # 5. Impute missing
        df, report = self._step_impute(df, report)

        # 6. Cap outliers
        df, report = self._step_cap_outliers(df, report)

        # 7. Log-transform skewed
        df, report = self._step_log_transform(df, report)

        # 8. Encode categoricals
        df, report = self._step_encode_categoricals(df, sem_map, report)

        # 9. Scale numerics
        df, report = self._step_scale(df, report)

        report.final_shape       = df.shape
        report.feature_names_out = [c for c in df.columns if c != self._target_col]
        self._feature_names_out  = report.feature_names_out
        return df, report

    def transform_new(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replay all fitted transforms on new/inference data."""
        if self._report is None:
            raise RuntimeError("Call fit_transform() first")
        df = df.copy()

        # Drop same cols
        drop = [c for c in self._drop_cols if c in df.columns]
        df.drop(columns=drop, inplace=True)

        # Datetime → numeric
        for col in self._report.steps:
            pass  # handled implicitly via column presence

        # Coerce numerics
        for col in df.select_dtypes(include="object").columns:
            if col == self._target_col:
                continue
            df[col] = _safe_to_numeric(df[col])

        # Impute
        for col, val in self._impute_values.items():
            if col in df.columns:
                df[col] = df[col].fillna(val)

        # Cap outliers (replay stored bounds)
        for step in self._report.steps:
            if step.step_name == "cap_outliers":
                for col, bounds in step.metadata.items():
                    if col in df.columns:
                        df[col] = df[col].clip(bounds["lo"], bounds["hi"])

        # Log-transform
        for col in self._log_cols:
            if col in df.columns:
                df[col] = np.log1p(df[col].clip(0))

        # Ordinal encode
        for col, enc in self._ordinal_enc.items():
            if col in df.columns:
                df[col] = enc.transform(
                    df[col].astype(str).str.lower().values.reshape(-1, 1)
                ).ravel()

        # OHE
        for col in self._ohe_cols:
            if col in df.columns:
                cats = self._ohe_categories[col]
                dummies = pd.get_dummies(df[col].astype(str), prefix=col, dtype=float)
                for cat in cats:
                    cname = f"{col}_{cat}"
                    if cname not in dummies.columns:
                        dummies[cname] = 0.0
                dummies = dummies[[c for c in cats if c in dummies.columns
                                   or True]].reindex(
                    columns=[f"{col}_{c}" for c in cats], fill_value=0.0)
                df.drop(columns=[col], inplace=True)
                df = pd.concat([df, dummies], axis=1)

        # Label encode
        for col, enc in self._label_enc.items():
            if col in df.columns:
                df[col] = df[col].astype(str).map(
                    {v: i for i, v in enumerate(enc.classes_)}
                ).fillna(-1).astype(int)

        # Scale
        if self._scaler and self._scale_cols:
            present = [c for c in self._scale_cols if c in df.columns]
            df[present] = self._scaler.transform(df[present].values)

        return df

    # ── private steps ────────────────────────────────────────────────────────

    def _step_drop_junk(self, df: pd.DataFrame, sem_map: SemanticMap,
                         report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        to_drop: List[str] = []

        for col in df.columns:
            # constant
            if df[col].nunique(dropna=True) <= 1:
                to_drop.append(col)
                continue
            # >60% missing
            if df[col].isna().mean() >= MISSING_DROP_THRESHOLD:
                to_drop.append(col)
                continue
            # ID-like (unique_rate > 95%)
            m = sem_map.mappings.get(col)
            if m and m.semantic_category == "employee_id":
                to_drop.append(col)
                continue
            ur = df[col].nunique(dropna=True) / max(len(df[col].dropna()), 1)
            if ur > 0.95 and not pd.api.types.is_numeric_dtype(df[col]):
                to_drop.append(col)

        to_drop = list(set(to_drop))
        # Never drop target
        if self._target_col in to_drop:
            to_drop.remove(self._target_col)

        df.drop(columns=to_drop, errors="ignore", inplace=True)
        self._drop_cols = to_drop
        report.dropped_columns = to_drop
        report.steps.append(HealStep(
            step_name        = "drop_junk",
            columns_affected = to_drop,
            description      = f"Dropped {len(to_drop)} columns (constant/missing/ID-like)",
        ))
        return df, report

    def _step_parse_datetimes(self, df: pd.DataFrame, sem_map: SemanticMap,
                               report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        affected = []
        for col in list(df.columns):
            m = sem_map.mappings.get(col)
            if m and m.semantic_category == "timestamp":
                try:
                    parsed = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
                    if parsed.notna().mean() > 0.5:
                        ref = parsed.min()
                        df[col + "_days"] = (parsed - ref).dt.days
                        df[col + "_month"] = parsed.dt.month
                        df[col + "_year"]  = parsed.dt.year
                        df.drop(columns=[col], inplace=True)
                        affected.append(col)
                except Exception:
                    pass
        if affected:
            report.steps.append(HealStep(
                step_name        = "parse_datetimes",
                columns_affected = affected,
                description      = f"Converted {len(affected)} datetime cols → numeric features",
            ))
        return df, report

    def _step_encode_target(self, df: pd.DataFrame,
                             report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        tc = self._target_col
        if tc not in df.columns:
            return df, report

        series = df[tc]
        if pd.api.types.is_numeric_dtype(series):
            # already numeric; ensure 0/1
            unique = sorted(series.dropna().unique())
            if set(unique) <= {0, 1}:
                self._target_map = {0: 0, 1: 1}
                report.target_encoding = self._target_map
                return df, report
            # map to 0..n-1
            mapping = {v: i for i, v in enumerate(unique)}
        else:
            vals = series.astype(str).str.lower().str.strip()
            # Binary positive-detection
            unique_v = vals.dropna().unique()
            pos_candidates = [v for v in unique_v if v in _TARGET_POSITIVE]
            neg_candidates = [v for v in unique_v if v not in _TARGET_POSITIVE]
            if len(pos_candidates) == 1 and len(neg_candidates) == 1:
                mapping = {neg_candidates[0]: 0, pos_candidates[0]: 1}
            else:
                # fallback: alphabetical 0-indexed
                mapping = {v: i for i, v in enumerate(sorted(unique_v))}
            df[tc] = vals

        df[tc] = df[tc].map(mapping).fillna(-1).astype(int)
        self._target_map = mapping
        report.target_encoding = mapping
        report.steps.append(HealStep(
            step_name        = "encode_target",
            columns_affected = [tc],
            description      = f"Encoded target '{tc}' → 0/1 via {mapping}",
        ))
        return df, report

    def _step_coerce_numerics(self, df: pd.DataFrame,
                               report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        affected = []
        for col in df.select_dtypes(include="object").columns:
            if col == self._target_col:
                continue
            coerced = _safe_to_numeric(df[col])
            # Only accept if >50% converted
            if coerced.notna().mean() > 0.50:
                df[col] = coerced
                affected.append(col)
        if affected:
            report.steps.append(HealStep(
                step_name        = "coerce_numerics",
                columns_affected = affected,
                description      = f"Coerced {len(affected)} object cols → numeric",
            ))
        return df, report

    def _step_impute(self, df: pd.DataFrame,
                     report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        affected = []
        for col in df.columns:
            if col == self._target_col:
                continue
            miss_rate = df[col].isna().mean()
            if miss_rate == 0:
                continue

            if pd.api.types.is_numeric_dtype(df[col]):
                fill = df[col].median()
                method = "median"
            else:
                vc = df[col].value_counts()
                fill = vc.index[0] if len(vc) > 0 else "Unknown"
                method = "mode"

            df[col] = df[col].fillna(fill)
            self._impute_values[col] = fill
            affected.append(col)
            report.imputed_columns[col] = fill

        if affected:
            report.steps.append(HealStep(
                step_name        = "impute_missing",
                columns_affected = affected,
                description      = f"Imputed {len(affected)} columns (median/mode)",
            ))
        return df, report

    def _step_cap_outliers(self, df: pd.DataFrame,
                            report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        bounds_meta: Dict[str, Dict] = {}
        affected = []
        for col in df.select_dtypes(include=[np.number]).columns:
            if col == self._target_col:
                continue
            q1, q3 = df[col].quantile([0.25, 0.75])
            iqr    = q3 - q1
            lo     = q1 - OUTLIER_IQR_FACTOR * iqr
            hi     = q3 + OUTLIER_IQR_FACTOR * iqr
            n_out  = ((df[col] < lo) | (df[col] > hi)).sum()
            if n_out > 0:
                df[col] = df[col].clip(lo, hi)
                bounds_meta[col] = {"lo": float(lo), "hi": float(hi)}
                affected.append(col)
        if affected:
            report.steps.append(HealStep(
                step_name        = "cap_outliers",
                columns_affected = affected,
                description      = f"Capped outliers in {len(affected)} numeric cols (IQR×{OUTLIER_IQR_FACTOR})",
                metadata         = bounds_meta,
            ))
        return df, report

    def _step_log_transform(self, df: pd.DataFrame,
                             report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        affected = []
        for col in df.select_dtypes(include=[np.number]).columns:
            if col == self._target_col:
                continue
            s = df[col].dropna()
            if len(s) == 0 or s.min() < 0:
                continue
            skew = float(s.skew())
            if abs(skew) > NUMERIC_SKEW_THRESHOLD:
                df[col] = np.log1p(df[col].clip(0))
                self._log_cols.append(col)
                affected.append(col)
        if affected:
            report.log_transformed = affected
            report.steps.append(HealStep(
                step_name        = "log_transform",
                columns_affected = affected,
                description      = f"log1p-transformed {len(affected)} high-skew columns",
            ))
        return df, report

    def _step_encode_categoricals(self, df: pd.DataFrame, sem_map: SemanticMap,
                                   report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        cat_cols = [c for c in cat_cols if c != self._target_col]

        ohe_done: List[str] = []
        ord_done: List[str] = []
        lbl_done: List[str] = []

        for col in cat_cols:
            n_u = df[col].nunique(dropna=True)
            order = _detect_ordinal(df[col])

            if order:
                # ordinal encoding
                df[col] = df[col].astype(str).str.lower().str.strip()
                enc = OrdinalEncoder(
                    categories=[order],
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                )
                df[col] = enc.fit_transform(df[[col]]).ravel()
                self._ordinal_enc[col] = enc
                ord_done.append(col)
                report.encoded_columns[col] = "ordinal"

            elif n_u <= CARDINALITY_HIGH:
                # one-hot encoding
                cats = sorted(df[col].dropna().astype(str).unique().tolist())
                dummies = pd.get_dummies(df[col].astype(str), prefix=col, dtype=float)
                df.drop(columns=[col], inplace=True)
                df = pd.concat([df, dummies], axis=1)
                self._ohe_cols.append(col)
                self._ohe_categories[col] = [f"{col}_{c}" for c in cats]
                ohe_done.append(col)
                report.encoded_columns[col] = f"one_hot ({n_u} cats)"

            else:
                # high-cardinality: label encode
                enc = LabelEncoder()
                df[col] = enc.fit_transform(df[col].astype(str))
                self._label_enc[col] = enc
                lbl_done.append(col)
                report.encoded_columns[col] = f"label ({n_u} cats)"

        all_affected = ohe_done + ord_done + lbl_done
        if all_affected:
            report.steps.append(HealStep(
                step_name        = "encode_categoricals",
                columns_affected = all_affected,
                description      = (f"Encoded categoricals: "
                                    f"{len(ohe_done)} OHE, "
                                    f"{len(ord_done)} ordinal, "
                                    f"{len(lbl_done)} label"),
            ))
        return df, report

    def _step_scale(self, df: pd.DataFrame,
                    report: HealReport) -> Tuple[pd.DataFrame, HealReport]:
        num_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                    if c != self._target_col]
        if not num_cols:
            return df, report

        if self._scaler_type == "standard":
            scaler = StandardScaler()
        else:
            scaler = RobustScaler()

        df[num_cols] = scaler.fit_transform(df[num_cols].values)
        self._scaler      = scaler
        self._scale_cols  = num_cols
        report.scaled_columns = num_cols
        report.steps.append(HealStep(
            step_name        = "scale_numerics",
            columns_affected = num_cols,
            description      = f"{self._scaler_type.title()}Scaler applied to {len(num_cols)} numeric cols",
        ))
        return df, report
