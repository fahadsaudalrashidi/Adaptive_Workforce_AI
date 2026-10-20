"""
Feature Trustworthiness Assessment
=====================================
Evaluates whether top predictive features are scientifically credible
or whether they carry cardinality risk, leakage risk, or dominance risk.

Output:
  FeatureTrustworthinessReport with per-feature assessments.

Key rules:
  - High-cardinality categorical features get a "Caution" flag
  - Features with importance share > 40% trigger dominance warning
  - All language is associative ("associated with"), never causal
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from sklearn.feature_selection import mutual_info_classif
    _HAS_MI = True
except ImportError:
    _HAS_MI = False

from config.settings import (
    HC_DOMINANCE_WARN_THRESHOLD,
    HC_DOMINANCE_FLAG_THRESHOLD,
    HC_UNIQUE_RATIO_RISK,
    CARDINALITY_HIGH,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

TRUST_RELIABLE  = "Reliable"
TRUST_CAUTION   = "Interpret with Caution"
TRUST_HIGH_RISK = "High Risk — Validate"

# Safe associative language templates
_ASSOC_NOTE = (
    "{feature} is associated with predicted risk in this dataset. "
    "This association may reflect historical patterns and does not imply a causal relationship."
)
_HC_NOTE = (
    "{feature} is a high-cardinality categorical feature ({n_unique} unique values, "
    "{unique_ratio:.0%} unique ratio). High-cardinality features can capture role-specific "
    "historical patterns rather than generalizable causal drivers. "
    "Interpret this predictor with caution."
)
_DOMINANCE_NOTE = (
    "{feature} accounts for {share:.0%} of total feature importance — unusually high. "
    "Single-feature dominance may indicate data-specific patterns or memorization effects. "
    "Model performance should be validated on held-out data before deployment."
)


# ─────────────────────────────────────────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeatureTrustAssessment:
    feature_name: str
    importance_score: float
    importance_share: float          # fraction of total importance
    dtype: str                       # "numeric" / "categorical"
    n_unique: int
    unique_ratio: float              # n_unique / n_rows
    cardinality_risk: str            # "Low" / "Moderate" / "High"
    dominance_risk: str              # "None" / "Warning" / "Flag"
    leakage_risk: str                # "None" / "Low" / "High"
    trust_level: str                 # TRUST_*
    associative_note: str            # always non-causal language
    recommendation: str


@dataclass
class FeatureTrustworthinessReport:
    assessments: List[FeatureTrustAssessment]
    top_feature_name: str
    top_feature_share: float
    has_dominance_warning: bool
    has_cardinality_risk: bool
    overall_trust: str               # "Reliable" / "Caution" / "High Risk"
    summary: str
    recommendations: List[str]
    # Whether model reliability should be downgraded
    downgrade_model_reliability: bool
    downgrade_reason: str


# ─────────────────────────────────────────────────────────────────────────────
# ASSESSOR
# ─────────────────────────────────────────────────────────────────────────────

class FeatureTrustworthinessAssessor:

    def assess(
        self,
        df: pd.DataFrame,
        feature_names: List[str],
        target_col: Optional[str],
        feature_importances: Optional[Dict[str, float]],
    ) -> FeatureTrustworthinessReport:

        if not feature_names:
            return self._empty_report()

        n_rows = len(df)
        assessments: List[FeatureTrustAssessment] = []
        total_importance = sum(feature_importances.values()) if feature_importances else 0.0
        if total_importance == 0:
            total_importance = 1.0

        for feat in feature_names:
            if feat not in df.columns:
                continue

            col = df[feat]
            imp = feature_importances.get(feat, 0.0) if feature_importances else 0.0
            share = imp / total_importance

            # Dtype — handle pandas 3.0 StringDtype ("str") and legacy "object"
            is_cat = (
                col.dtype == object
                or str(col.dtype) == "category"
                or str(col.dtype) == "str"
                or str(col.dtype).startswith("string")
                or not (pd.api.types.is_numeric_dtype(col) or pd.api.types.is_datetime64_any_dtype(col))
            )
            dtype_label = "categorical" if is_cat else "numeric"

            n_unique = int(col.nunique(dropna=True))
            unique_ratio = n_unique / max(n_rows, 1)

            # Cardinality risk
            if is_cat:
                if unique_ratio > HC_UNIQUE_RATIO_RISK or n_unique > CARDINALITY_HIGH:
                    card_risk = "High"
                elif n_unique > 10:
                    card_risk = "Moderate"
                else:
                    card_risk = "Low"
            else:
                card_risk = "Low"

            # Dominance risk
            if share > HC_DOMINANCE_FLAG_THRESHOLD:
                dom_risk = "Flag"
            elif share > HC_DOMINANCE_WARN_THRESHOLD:
                dom_risk = "Warning"
            else:
                dom_risk = "None"

            # Basic leakage risk (very high correlation with target)
            leakage_risk = "None"
            if target_col and target_col in df.columns:
                try:
                    if not is_cat:
                        corr = abs(float(pd.to_numeric(col, errors="coerce")
                                         .corr(pd.to_numeric(df[target_col], errors="coerce"))))
                        if corr > 0.95:
                            leakage_risk = "High"
                        elif corr > 0.80:
                            leakage_risk = "Low"
                except Exception:
                    pass

            # Trust level
            if leakage_risk == "High" or dom_risk == "Flag":
                trust = TRUST_HIGH_RISK
            elif card_risk == "High" or dom_risk == "Warning":
                trust = TRUST_CAUTION
            else:
                trust = TRUST_RELIABLE

            # Associative note (never causal)
            if card_risk == "High":
                note = _HC_NOTE.format(feature=feat, n_unique=n_unique, unique_ratio=unique_ratio)
            elif dom_risk in ("Flag", "Warning"):
                note = _DOMINANCE_NOTE.format(feature=feat, share=share)
            else:
                note = _ASSOC_NOTE.format(feature=feat)

            # Recommendation
            if leakage_risk == "High":
                rec = f"Remove '{feat}' — it is nearly perfectly correlated with the target."
            elif dom_risk == "Flag":
                rec = f"'{feat}' dominates predictions ({share:.0%} importance). Validate on unseen data and consider re-training without this feature."
            elif card_risk == "High":
                rec = f"'{feat}' has high cardinality ({n_unique} unique values). Validate whether it generalises or merely memorises training patterns."
            else:
                rec = f"'{feat}' appears reliable. Standard cross-validation applies."

            assessments.append(FeatureTrustAssessment(
                feature_name     = feat,
                importance_score = round(imp, 4),
                importance_share = round(share, 4),
                dtype            = dtype_label,
                n_unique         = n_unique,
                unique_ratio     = round(unique_ratio, 4),
                cardinality_risk = card_risk,
                dominance_risk   = dom_risk,
                leakage_risk     = leakage_risk,
                trust_level      = trust,
                associative_note = note,
                recommendation   = rec,
            ))

        if not assessments:
            return self._empty_report()

        # Sort by importance
        assessments.sort(key=lambda a: a.importance_score, reverse=True)

        top = assessments[0]
        has_dom = any(a.dominance_risk in ("Warning", "Flag") for a in assessments)
        has_card = any(a.cardinality_risk == "High" for a in assessments)
        has_leakage = any(a.leakage_risk == "High" for a in assessments)

        if has_leakage or any(a.trust_level == TRUST_HIGH_RISK for a in assessments):
            overall = TRUST_HIGH_RISK
        elif has_dom or has_card:
            overall = TRUST_CAUTION
        else:
            overall = TRUST_RELIABLE

        recs = list(dict.fromkeys(a.recommendation for a in assessments
                                   if a.trust_level != TRUST_RELIABLE))[:5]
        if not recs:
            recs = ["Feature trustworthiness appears acceptable. Monitor on new data."]

        downgrade = has_leakage or top.dominance_risk == "Flag"
        downgrade_reason = ""
        if has_leakage:
            downgrade_reason = "Direct target leakage detected in feature set."
        elif top.dominance_risk == "Flag":
            downgrade_reason = (
                f"'{top.feature_name}' accounts for {top.importance_share:.0%} of feature importance — "
                "single-feature dominance may indicate overfitting."
            )

        summary = (
            f"Top predictor: '{top.feature_name}' ({top.importance_share:.0%} importance share, "
            f"{top.cardinality_risk.lower()} cardinality risk). "
            f"Overall feature trust: {overall}."
        )

        return FeatureTrustworthinessReport(
            assessments                = assessments,
            top_feature_name           = top.feature_name,
            top_feature_share          = top.importance_share,
            has_dominance_warning      = has_dom,
            has_cardinality_risk       = has_card,
            overall_trust              = overall,
            summary                    = summary,
            recommendations            = recs,
            downgrade_model_reliability = downgrade,
            downgrade_reason           = downgrade_reason,
        )

    @staticmethod
    def _empty_report() -> FeatureTrustworthinessReport:
        return FeatureTrustworthinessReport(
            assessments=[], top_feature_name="", top_feature_share=0.0,
            has_dominance_warning=False, has_cardinality_risk=False,
            overall_trust=TRUST_RELIABLE, summary="No features available for assessment.",
            recommendations=[], downgrade_model_reliability=False, downgrade_reason="",
        )
