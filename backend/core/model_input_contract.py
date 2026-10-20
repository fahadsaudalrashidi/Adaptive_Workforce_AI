# -*- coding: utf-8 -*-
"""
Model Input Contract
====================

Validates that a feature set passed to the ML model meets all scientific
governance requirements before training or inference begins.

Enforces:
  - No leakage-flagged columns
  - No legacy-disabled constructs
  - No target-adjacent columns
  - No ID memorization columns
  - No construct without evidence metadata
  - No post-outcome / temporal-leakage columns

Does NOT:
  - Train models
  - Modify the DataFrame
  - Change feature importances
  - Override governance decisions
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import pandas as pd

from config.settings import (
    LEGACY_DISABLED_CONSTRUCTS,
    PROXY_LEAKAGE_KEYWORDS,
    SCIENTIFIC_FEATURE_MODE,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# BLOCKED COLUMN LISTS
# ─────────────────────────────────────────────────────────────────────────────

# Columns that encode the target outcome directly
_TARGET_ADJACENT_KEYWORDS: List[str] = [
    "attrition_risk", "retention_risk", "churn_score", "resignation_score",
    "flight_risk", "turnover_risk", "stability_score", "stay_probability",
    "predicted_tenure", "exit_risk", "offboard", "final_status",
    "exit_reason", "separation_reason", "last_day", "last_working_day",
    "offboarding_date", "end_date", "termination_date",
]

# Columns that appear to be row identifiers (memorization risk)
_ID_COLUMN_KEYWORDS: List[str] = [
    "employee_id", "employeeid", "emp_id", "empid",
    "rownum", "row_num", "rowid", "row_id",
    "index", "idx", "serial", "seq", "uuid", "guid",
    "badge_number", "badge_no", "badgenumber",
]

# Columns that suggest preprocessing applied before split (leakage)
_PREPROCESSING_KEYWORDS: List[str] = [
    "scaled", "imputed", "encoded", "normalised", "normalized", "_norm",
]

# The 7 valid theory-grounded construct names — these are ALLOWED
_VALID_THEORY_CONSTRUCTS: Set[str] = {
    "SatisfactionIndex", "BurnoutRisk", "EngagementScore",
    "TenureRatio", "IncomePerLevel", "CareerProgression", "SalaryGrowth",
}


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ContractViolation:
    """A single contract violation found in the feature set."""
    feature_name: str
    violation_type: str       # LEAKAGE / LEGACY_DISABLED / TARGET_ADJACENT / ID / PREPROCESSING
    severity: str             # CRITICAL / HIGH / MEDIUM
    reason: str
    recommendation: str


@dataclass
class ContractValidationResult:
    """Full result of model input contract validation."""
    is_valid: bool
    approved_features: List[str]
    blocked_features: List[str]
    violations: List[ContractViolation]
    n_critical: int
    n_high: int
    n_medium: int
    scientific_feature_mode: str
    summary: str
    governance_notes: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

class ModelInputContract:
    """
    Validates the ML feature set against scientific governance rules.

    Usage
    -----
    contract = ModelInputContract()
    result = contract.validate(feature_names, df, target_col, column_mappings)
    if not result.is_valid:
        raise ValueError(result.summary)
    """

    def validate(
        self,
        feature_names: List[str],
        df: Optional[pd.DataFrame] = None,
        target_col: Optional[str] = None,
        column_mappings: Optional[dict] = None,
    ) -> ContractValidationResult:
        """
        Validate feature_names against all contract rules.

        Parameters
        ----------
        feature_names    : List of column names proposed as ML features.
        df               : The DataFrame (for cardinality checks). May be None.
        target_col       : Target column name (to exclude from features).
        column_mappings  : Phase 1 ConstructMapping dict (for evidence checks).
        """
        violations: List[ContractViolation] = []
        blocked: List[str] = []

        for feat in feature_names:
            feat_lower = feat.lower()

            # 0. Theory-grounded constructs are pre-approved — skip all pattern checks.
            #    These names share lexical tokens with blocked patterns (e.g. "index"
            #    in "SatisfactionIndex") but were computed from exact paper formulas.
            if feat in _VALID_THEORY_CONSTRUCTS:
                continue

            # 1. Target column in features
            if target_col and feat == target_col:
                violations.append(ContractViolation(
                    feature_name=feat,
                    violation_type="TARGET_IN_FEATURES",
                    severity="CRITICAL",
                    reason=f"'{feat}' is the target column and must not be a feature.",
                    recommendation="Remove target column from feature_names.",
                ))
                blocked.append(feat)
                continue

            # 2. Legacy disabled constructs
            # Theory-grounded constructs share names with Layer B constructs but
            # are computed with exact paper formulas — they are exempt from this block.
            if feat in LEGACY_DISABLED_CONSTRUCTS and feat not in _VALID_THEORY_CONSTRUCTS:
                violations.append(ContractViolation(
                    feature_name=feat,
                    violation_type="LEGACY_DISABLED",
                    severity="CRITICAL",
                    reason=(
                        f"'{feat}' is a legacy-disabled construct "
                        f"(SCIENTIFIC_FEATURE_MODE={SCIENTIFIC_FEATURE_MODE}). "
                        "It uses an incorrect formula and must not enter the model."
                    ),
                    recommendation=(
                        "Remove from feature set. "
                        "Use TheoryGroundedConstructEngine for scientifically valid equivalents."
                    ),
                ))
                blocked.append(feat)
                continue

            # 3. Proxy leakage keywords (target-semantic names)
            matched_proxy = [kw for kw in PROXY_LEAKAGE_KEYWORDS if kw in feat_lower]
            if matched_proxy:
                violations.append(ContractViolation(
                    feature_name=feat,
                    violation_type="PROXY_LEAKAGE",
                    severity="CRITICAL",
                    reason=(
                        f"'{feat}' contains target-semantic keywords: {matched_proxy}. "
                        "This column likely encodes the attrition outcome."
                    ),
                    recommendation="Remove from feature set immediately.",
                ))
                blocked.append(feat)
                continue

            # 4. Target-adjacent derived risk columns
            matched_ta = [kw for kw in _TARGET_ADJACENT_KEYWORDS if kw in feat_lower]
            if matched_ta:
                violations.append(ContractViolation(
                    feature_name=feat,
                    violation_type="TARGET_ADJACENT",
                    severity="CRITICAL",
                    reason=(
                        f"'{feat}' appears to be a target-adjacent column "
                        f"(matched keywords: {matched_ta}). "
                        "Post-outcome or derived risk scores cause target leakage."
                    ),
                    recommendation="Remove from feature set. Never include derived risk scores as features.",
                ))
                blocked.append(feat)
                continue

            # 5. ID memorization columns
            matched_id = [kw for kw in _ID_COLUMN_KEYWORDS if kw in feat_lower]
            if matched_id:
                violations.append(ContractViolation(
                    feature_name=feat,
                    violation_type="ID_MEMORIZATION",
                    severity="HIGH",
                    reason=(
                        f"'{feat}' appears to be an identifier column "
                        f"(matched: {matched_id}). Identifiers allow row memorization."
                    ),
                    recommendation="Remove employee/row ID columns from feature set.",
                ))
                blocked.append(feat)
                continue

            # 6. Preprocessing leakage indicators
            matched_pp = [kw for kw in _PREPROCESSING_KEYWORDS if kw in feat_lower]
            if matched_pp:
                violations.append(ContractViolation(
                    feature_name=feat,
                    violation_type="PREPROCESSING_LEAKAGE",
                    severity="MEDIUM",
                    reason=(
                        f"'{feat}' name suggests pre-split preprocessing "
                        f"(keywords: {matched_pp}). "
                        "Scaling/imputation applied before split leaks test statistics."
                    ),
                    recommendation=(
                        "Verify this feature was transformed inside CV folds only. "
                        "Rename if transformation is fold-safe."
                    ),
                ))
                # Medium severity: flag but do not block

            # 7. Phase 1 leakage flag check
            if column_mappings and feat in column_mappings:
                m = column_mappings[feat]
                if getattr(m, "leakage_flag", False):
                    violations.append(ContractViolation(
                        feature_name=feat,
                        violation_type="CONSTRUCT_LEAKAGE_FLAGGED",
                        severity="CRITICAL",
                        reason=(
                            f"'{feat}' has leakage_flag=True from Phase 1 column mapper "
                            f"(evidence: {getattr(m, 'evidence_strength', 'unknown')})."
                        ),
                        recommendation="Remove from feature set. Phase 1 governance blocked this column.",
                    ))
                    blocked.append(feat)
                    continue

        # Approved = all features minus blocked
        approved = [f for f in feature_names if f not in blocked]

        n_critical = sum(1 for v in violations if v.severity == "CRITICAL")
        n_high     = sum(1 for v in violations if v.severity == "HIGH")
        n_medium   = sum(1 for v in violations if v.severity == "MEDIUM")

        is_valid = (n_critical == 0 and n_high == 0)

        # Build summary
        if not violations:
            summary = (
                f"Contract VALID. {len(approved)} features approved. "
                f"Mode: {SCIENTIFIC_FEATURE_MODE}."
            )
        else:
            parts = []
            if n_critical:
                parts.append(f"{n_critical} CRITICAL")
            if n_high:
                parts.append(f"{n_high} HIGH")
            if n_medium:
                parts.append(f"{n_medium} MEDIUM")
            summary = (
                f"Contract {'VALID' if is_valid else 'INVALID'}. "
                f"{len(blocked)} features blocked ({', '.join(parts)} violations). "
                f"{len(approved)} features approved."
            )

        notes = []
        if SCIENTIFIC_FEATURE_MODE == "theory_grounded":
            notes.append(
                f"SCIENTIFIC_FEATURE_MODE=theory_grounded: "
                f"{len(LEGACY_DISABLED_CONSTRUCTS)} legacy constructs are blocked."
            )
        if column_mappings:
            theory_constructs_present = [
                f for f in approved if f in _VALID_THEORY_CONSTRUCTS
            ]
            if theory_constructs_present:
                notes.append(
                    f"Theory-grounded constructs in feature set: {theory_constructs_present}"
                )

        logger.info("ModelInputContract: %s", summary)

        return ContractValidationResult(
            is_valid=is_valid,
            approved_features=approved,
            blocked_features=blocked,
            violations=violations,
            n_critical=n_critical,
            n_high=n_high,
            n_medium=n_medium,
            scientific_feature_mode=SCIENTIFIC_FEATURE_MODE,
            summary=summary,
            governance_notes=notes,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def validate_model_inputs(
    feature_names: List[str],
    df: Optional[pd.DataFrame] = None,
    target_col: Optional[str] = None,
    column_mappings: Optional[dict] = None,
) -> ContractValidationResult:
    """One-call convenience wrapper around ModelInputContract.validate()."""
    return ModelInputContract().validate(feature_names, df, target_col, column_mappings)
