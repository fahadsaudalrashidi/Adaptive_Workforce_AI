# -*- coding: utf-8 -*-
"""
Temporal Validation Guard
=========================

Detects temporal leakage and unsafe split strategies in HR datasets
before training begins.

Enforces:
  - Exit/post-outcome date columns are identified and blocked from features
  - Hire/start dates that could proxy tenure (but are not the target) are warned
  - Random split is flagged as unsafe when temporal columns are present
  - SMOTE and preprocessing-before-split are detected and flagged
  - Datasets with any date column receive a mandatory time-aware split advisory

Does NOT:
  - Modify the DataFrame
  - Change the model or split
  - Block training (returns findings; caller decides)
  - Override governance decisions made upstream
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN PATTERN LIBRARIES
# ─────────────────────────────────────────────────────────────────────────────

# Post-outcome / exit dates — always leakage risk as features
_EXIT_DATE_PATTERNS: List[str] = [
    "exit_date", "exitdate",
    "resignation_date", "resignationdate", "resigned_date",
    "last_day", "lastday", "last_working_day", "lastworkingday",
    "offboarding_date", "offboardingdate",
    "termination_date", "terminationdate",
    "end_date", "enddate",
    "final_status_date", "departure_date", "deparaturedate",
    "separation_date", "separationdate",
    "leave_date", "leavedate",
    "employment_end", "employmentend",
]

# Hire / start dates — may proxy tenure; flag for review but not always blocked
_HIRE_DATE_PATTERNS: List[str] = [
    "hire_date", "hiredate", "hired_date",
    "start_date", "startdate", "joining_date", "joiningdate",
    "employment_start", "employmentstart",
    "onboarding_date", "onboardingdate",
    "date_joined", "datejoined",
    "first_day", "firstday",
]

# Generic date / time column identifiers
_GENERIC_DATE_PATTERNS: List[str] = [
    "_date", "date_", "_dt", "dt_", "_time", "time_",
    "_month", "_year", "_quarter",
    "snapshot_", "_snapshot", "as_of_",
    "period", "fiscal_",
]

# Columns that store the survey / data collection snapshot
_SNAPSHOT_PATTERNS: List[str] = [
    "survey_date", "surveydate", "data_date", "snapshot_date",
    "report_date", "reportdate", "extraction_date",
    "as_of_date", "reference_date",
]

# Preprocessing keywords in column names that suggest pre-split transformation
_PREPROCESSING_COLUMN_KEYWORDS: List[str] = [
    "_scaled", "_imputed", "_encoded", "_normalised", "_normalized",
    "_norm", "_std", "_zscore",
]


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TemporalFinding:
    """A single temporal leakage or split-safety finding."""
    column_name: str
    finding_type: str    # EXIT_DATE / HIRE_DATE / GENERIC_DATE / SNAPSHOT / PREPROCESSING_LEAK
    severity: str        # CRITICAL / HIGH / MEDIUM / INFO
    reason: str
    recommendation: str


@dataclass
class SplitSafetyAssessment:
    """Whether a random split is safe given temporal columns in the dataset."""
    random_split_safe: bool
    reason: str
    recommended_strategy: str          # "random" / "time_based" / "stratified_time"
    temporal_columns_detected: List[str]
    exit_columns_detected: List[str]
    hire_columns_detected: List[str]


@dataclass
class TemporalValidationReport:
    """Full output of temporal validation guard."""
    has_temporal_risk: bool
    random_split_safe: bool
    n_critical: int
    n_high: int
    n_medium: int
    n_info: int
    findings: List[TemporalFinding]
    split_assessment: SplitSafetyAssessment
    preprocessing_leak_columns: List[str]
    exit_date_columns: List[str]
    hire_date_columns: List[str]
    generic_date_columns: List[str]
    snapshot_columns: List[str]
    summary: str
    governance_notes: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# GUARD
# ─────────────────────────────────────────────────────────────────────────────

class TemporalValidationGuard:
    """
    Scans a feature set and DataFrame for temporal leakage and unsafe split
    configurations.

    Usage
    -----
    guard = TemporalValidationGuard()
    report = guard.validate(feature_names, df, target_col)
    if not report.random_split_safe:
        logger.warning("Time-based split required: %s", report.summary)
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def validate(
        self,
        feature_names: List[str],
        df: Optional[pd.DataFrame] = None,
        target_col: Optional[str] = None,
        smote_before_split: bool = False,
        preprocessing_before_split: bool = False,
    ) -> TemporalValidationReport:
        """
        Validate feature_names for temporal leakage and split safety.

        Parameters
        ----------
        feature_names             : Proposed feature column names.
        df                        : The DataFrame (used for dtype sniffing). May be None.
        target_col                : Target column name (excluded from analysis).
        smote_before_split        : True if caller plans to apply SMOTE on full dataset
                                    before train/test split — always CRITICAL.
        preprocessing_before_split: True if caller plans to scale/impute before split.
        """
        findings: List[TemporalFinding] = []

        exit_cols: List[str] = []
        hire_cols: List[str] = []
        generic_date_cols: List[str] = []
        snapshot_cols: List[str] = []
        preprocess_leak_cols: List[str] = []

        # Also check all columns in df (not just features) for date presence
        all_cols = list(feature_names)
        if df is not None:
            all_cols = list(set(all_cols) | set(df.columns.tolist()))
        if target_col:
            all_cols = [c for c in all_cols if c != target_col]

        for col in all_cols:
            col_lower = col.lower()

            # 1. Exit / post-outcome dates
            if any(pat in col_lower for pat in _EXIT_DATE_PATTERNS):
                exit_cols.append(col)
                severity = "CRITICAL" if col in feature_names else "HIGH"
                findings.append(TemporalFinding(
                    column_name=col,
                    finding_type="EXIT_DATE",
                    severity=severity,
                    reason=(
                        f"'{col}' appears to be a post-outcome date column "
                        "(exit, resignation, termination, or offboarding date). "
                        "Including this as a feature causes direct temporal leakage — "
                        "the model sees information that only exists after the outcome occurs."
                    ),
                    recommendation=(
                        "Remove from feature set. "
                        "If temporal ordering is required, use it ONLY to define the "
                        "train/test split boundary, never as a model input."
                    ),
                ))
                continue

            # 2. Hire / start dates
            if any(pat in col_lower for pat in _HIRE_DATE_PATTERNS):
                hire_cols.append(col)
                findings.append(TemporalFinding(
                    column_name=col,
                    finding_type="HIRE_DATE",
                    severity="MEDIUM",
                    reason=(
                        f"'{col}' appears to be a hire or start date. "
                        "Raw date values proxy employee tenure and risk temporal leakage "
                        "if the snapshot date varies across rows. "
                        "Hire date itself is not a problem; using it without anchoring to "
                        "a fixed snapshot date is."
                    ),
                    recommendation=(
                        "Replace with derived tenure feature: "
                        "(snapshot_date − hire_date).days / 365. "
                        "Ensure snapshot_date is the same for all training rows."
                    ),
                ))
                continue

            # 3. Snapshot / report dates
            if any(pat in col_lower for pat in _SNAPSHOT_PATTERNS):
                snapshot_cols.append(col)
                findings.append(TemporalFinding(
                    column_name=col,
                    finding_type="SNAPSHOT",
                    severity="INFO",
                    reason=(
                        f"'{col}' appears to be a data snapshot or report date. "
                        "If all rows share the same snapshot date this is safe. "
                        "If rows span multiple snapshot periods, random split may "
                        "produce future-to-past leakage."
                    ),
                    recommendation=(
                        "Verify that all training rows share one snapshot date. "
                        "If multiple periods are present, use time-based split."
                    ),
                ))
                continue

            # 4. Generic date columns
            if any(pat in col_lower for pat in _GENERIC_DATE_PATTERNS):
                generic_date_cols.append(col)
                findings.append(TemporalFinding(
                    column_name=col,
                    finding_type="GENERIC_DATE",
                    severity="MEDIUM",
                    reason=(
                        f"'{col}' appears to contain date or time information. "
                        "Raw date columns used as numeric features encode temporal "
                        "order and may cause train/test leakage if not split correctly."
                    ),
                    recommendation=(
                        "Convert to a derived duration or cyclical feature. "
                        "Review whether random split is appropriate for this column."
                    ),
                ))
                continue

            # 5. Preprocessing leakage in column names
            if col in feature_names:
                matched_pp = [kw for kw in _PREPROCESSING_COLUMN_KEYWORDS if kw in col_lower]
                if matched_pp:
                    preprocess_leak_cols.append(col)
                    findings.append(TemporalFinding(
                        column_name=col,
                        finding_type="PREPROCESSING_LEAK",
                        severity="MEDIUM",
                        reason=(
                            f"'{col}' name suggests pre-split preprocessing "
                            f"(keywords: {matched_pp}). "
                            "Scaling or imputation applied to the full dataset before "
                            "splitting leaks test set statistics into training."
                        ),
                        recommendation=(
                            "Move all scaling, encoding, and imputation inside "
                            "cross-validation folds or after train/test split. "
                            "Rename the column if transformation is fold-safe."
                        ),
                    ))

        # 6. DataFrame dtype sniff for datetime columns not caught by name
        if df is not None:
            dt_cols = df.select_dtypes(include=["datetime", "datetime64"]).columns.tolist()
            for col in dt_cols:
                if (
                    col != target_col
                    and col not in exit_cols
                    and col not in hire_cols
                    and col not in snapshot_cols
                    and col not in generic_date_cols
                ):
                    generic_date_cols.append(col)
                    severity = "HIGH" if col in feature_names else "MEDIUM"
                    findings.append(TemporalFinding(
                        column_name=col,
                        finding_type="GENERIC_DATE",
                        severity=severity,
                        reason=(
                            f"'{col}' has dtype datetime64 — it encodes temporal order. "
                            "Including datetime columns as raw features causes temporal leakage."
                        ),
                        recommendation=(
                            "Extract meaningful duration features (days since event). "
                            "Use time-based train/test split if the column varies across rows."
                        ),
                    ))

        # 7. SMOTE before split — unconditional CRITICAL
        if smote_before_split:
            findings.append(TemporalFinding(
                column_name="SMOTE_PIPELINE",
                finding_type="SMOTE_BEFORE_SPLIT",
                severity="CRITICAL",
                reason=(
                    "SMOTE (or any over-sampling technique) is being applied BEFORE "
                    "train/test split. This leaks synthetic minority samples into the "
                    "test set, causing AUC inflation and invalid evaluation metrics."
                ),
                recommendation=(
                    "Apply SMOTE INSIDE cross-validation folds only, "
                    "using an imbalanced-learn Pipeline. "
                    "The test set must never contain SMOTE-generated rows."
                ),
            ))

        # 8. Preprocessing before split — unconditional CRITICAL
        if preprocessing_before_split:
            findings.append(TemporalFinding(
                column_name="PREPROCESSING_PIPELINE",
                finding_type="PREPROCESSING_BEFORE_SPLIT",
                severity="CRITICAL",
                reason=(
                    "Scaling, imputation, or encoding is being applied to the full dataset "
                    "BEFORE train/test split. This leaks test set statistics (mean, std, "
                    "quantiles) into training, inflating performance metrics."
                ),
                recommendation=(
                    "Fit all transformers on the training fold ONLY. "
                    "Apply (transform) to test fold without refitting. "
                    "Use sklearn Pipeline or ColumnTransformer inside CV."
                ),
            ))

        # ── Build split safety assessment ──────────────────────────────────
        all_temporal = exit_cols + hire_cols + generic_date_cols + snapshot_cols
        random_split_safe = len(exit_cols) == 0 and len(generic_date_cols) == 0

        if exit_cols:
            split_reason = (
                f"Dataset contains post-outcome date columns: {exit_cols}. "
                "Random split would allow future-date rows into training — "
                "temporal ordering of employment events is violated."
            )
            split_strategy = "time_based"
        elif hire_cols and not generic_date_cols:
            split_reason = (
                "Hire date columns are present but no exit/generic date columns. "
                "Random split is acceptable if all rows share one snapshot date; "
                "otherwise use time-based split."
            )
            split_strategy = "stratified_time"
            random_split_safe = True  # Cautiously allow with warning
        elif generic_date_cols:
            split_reason = (
                f"Date columns detected: {generic_date_cols}. "
                "Random split may violate temporal ordering depending on dataset structure."
            )
            split_strategy = "time_based"
        else:
            split_reason = "No temporal columns detected. Random split is acceptable."
            split_strategy = "random"

        split_assessment = SplitSafetyAssessment(
            random_split_safe=random_split_safe,
            reason=split_reason,
            recommended_strategy=split_strategy,
            temporal_columns_detected=all_temporal,
            exit_columns_detected=exit_cols,
            hire_columns_detected=hire_cols,
        )

        # ── Severity counts ────────────────────────────────────────────────
        n_critical = sum(1 for f in findings if f.severity == "CRITICAL")
        n_high     = sum(1 for f in findings if f.severity == "HIGH")
        n_medium   = sum(1 for f in findings if f.severity == "MEDIUM")
        n_info     = sum(1 for f in findings if f.severity == "INFO")

        has_temporal_risk = (n_critical > 0 or n_high > 0 or len(exit_cols) > 0)

        # ── Summary string ─────────────────────────────────────────────────
        if not findings:
            summary = (
                "No temporal leakage detected. "
                f"Random split is {'SAFE' if random_split_safe else 'NOT RECOMMENDED'}."
            )
        else:
            parts = []
            if n_critical:
                parts.append(f"{n_critical} CRITICAL")
            if n_high:
                parts.append(f"{n_high} HIGH")
            if n_medium:
                parts.append(f"{n_medium} MEDIUM")
            if n_info:
                parts.append(f"{n_info} INFO")
            summary = (
                f"Temporal validation: {', '.join(parts)} findings. "
                f"Random split {'SAFE' if random_split_safe else 'UNSAFE'}. "
                f"Recommended strategy: {split_strategy.upper()}."
            )

        # ── Governance notes ───────────────────────────────────────────────
        notes: List[str] = []
        if exit_cols:
            notes.append(
                f"EXIT DATE COLUMNS DETECTED: {exit_cols}. "
                "These columns must never appear in feature_names. "
                "They may only be used to construct the split boundary."
            )
        if smote_before_split:
            notes.append(
                "SMOTE BEFORE SPLIT: This configuration produces invalid AUC. "
                "All published metrics from this pipeline are unreliable."
            )
        if preprocessing_before_split:
            notes.append(
                "PREPROCESSING BEFORE SPLIT: All scaling/imputation statistics "
                "are contaminated. Metrics overstate real-world performance."
            )
        if hire_cols:
            notes.append(
                f"HIRE DATE COLUMNS: {hire_cols}. Convert to tenure duration "
                "features anchored to a fixed snapshot date before use."
            )

        logger.info("TemporalValidationGuard: %s", summary)

        return TemporalValidationReport(
            has_temporal_risk=has_temporal_risk,
            random_split_safe=random_split_safe,
            n_critical=n_critical,
            n_high=n_high,
            n_medium=n_medium,
            n_info=n_info,
            findings=findings,
            split_assessment=split_assessment,
            preprocessing_leak_columns=preprocess_leak_cols,
            exit_date_columns=exit_cols,
            hire_date_columns=hire_cols,
            generic_date_columns=generic_date_cols,
            snapshot_columns=snapshot_cols,
            summary=summary,
            governance_notes=notes,
        )

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #

    def is_random_split_safe(
        self,
        feature_names: List[str],
        df: Optional[pd.DataFrame] = None,
        target_col: Optional[str] = None,
    ) -> bool:
        """Quick boolean check — True if random split is acceptable."""
        report = self.validate(feature_names, df, target_col)
        return report.random_split_safe

    def get_exit_date_columns(
        self,
        columns: List[str],
    ) -> List[str]:
        """Return columns that match exit/post-outcome date patterns."""
        return [
            col for col in columns
            if any(pat in col.lower() for pat in _EXIT_DATE_PATTERNS)
        ]


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def validate_temporal_safety(
    feature_names: List[str],
    df: Optional[pd.DataFrame] = None,
    target_col: Optional[str] = None,
    smote_before_split: bool = False,
    preprocessing_before_split: bool = False,
) -> TemporalValidationReport:
    """One-call convenience wrapper around TemporalValidationGuard.validate()."""
    return TemporalValidationGuard().validate(
        feature_names, df, target_col,
        smote_before_split=smote_before_split,
        preprocessing_before_split=preprocessing_before_split,
    )
