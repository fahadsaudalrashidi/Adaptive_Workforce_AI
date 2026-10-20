"""
Feature Factory — Adaptive Feature Engineering Engine

Given a cleaned DataFrame and SemanticMap, automatically engineers domain-specific
psychological constructs and interaction features appropriate for the detected
dataset type. All new features are recorded in FeatureManifest for full
reproducibility.

Feature layers:
  A) Universal numeric interaction features (ratios, products, diffs)
  B) HR-specific constructs — LEGACY: DISABLED in theory_grounded mode
  C) Psychological constructs — LEGACY: DISABLED in theory_grounded mode
  D) Temporal features (tenure buckets, career velocity, etc.)
  E) Organizational features (workload pressure, managerial span, etc.)

SCIENTIFIC_FEATURE_MODE governance:
  "theory_grounded" (default): Layer B and C are disabled. Psychological constructs
    are computed by TheoryGroundedConstructEngine using exact paper formulas.
  "legacy_for_debug_only": Layer B and C run with explicit LEGACY_DISABLED warnings.
    Never use in production or reports.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from config.settings import DATASET_TYPES, SCIENTIFIC_FEATURE_MODE, LEGACY_DISABLED_CONSTRUCTS
from .semantic_mapper import SemanticMap

# Flag: True only when explicitly in debug/legacy mode — never in production
_LEGACY_MODE_ACTIVE = (SCIENTIFIC_FEATURE_MODE == "legacy_for_debug_only")


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeatureSpec:
    name: str
    formula: str             # human-readable description
    layer: str               # A/B/C/D/E
    requires: List[str]      # semantic categories needed
    is_construct: bool = False


@dataclass
class FeatureManifest:
    features_added: List[str] = field(default_factory=list)
    features_failed: List[str] = field(default_factory=list)
    specs_applied: List[FeatureSpec] = field(default_factory=list)
    n_original: int = 0
    n_final: int = 0
    legacy_constructs_disabled: List[str] = field(default_factory=list)
    scientific_feature_mode: str = SCIENTIFIC_FEATURE_MODE


# ─────────────────────────────────────────────────────────────────────────────
# SAFE COLUMN GETTER
# ─────────────────────────────────────────────────────────────────────────────

def _get_col(df: pd.DataFrame, sem_map: SemanticMap, category: str,
             numeric_only: bool = True) -> Optional[pd.Series]:
    """Return the first mapped column for a semantic category as a numeric Series."""
    cols = sem_map.get(category)
    for col in cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce") if numeric_only else df[col]
        if s.notna().mean() > 0.3:
            return s
    return None


def _norm(s: pd.Series) -> pd.Series:
    """Min-max normalise to [0, 1], NaN-safe."""
    mn, mx = s.min(), s.max()
    if mx - mn < 1e-9:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - mn) / (mx - mn)


def _clamp(s: pd.Series, lo: float = 0.0, hi: float = 1.0) -> pd.Series:
    return s.clip(lo, hi)


# ─────────────────────────────────────────────────────────────────────────────
# LAYER A — Universal numeric interactions
# ─────────────────────────────────────────────────────────────────────────────

def _layer_a_interactions(df: pd.DataFrame, sem_map: SemanticMap,
                           manifest: FeatureManifest) -> pd.DataFrame:
    """Safe pair-wise ratios and products for key numeric pairs."""
    pairs = [
        ("salary", "performance",  "pay_performance_ratio"),
        ("tenure", "age",          "career_start_age_proxy"),
        ("salary", "workload",     "pay_load_efficiency"),
        ("engagement", "burnout",  "engagement_burnout_gap"),
        ("satisfaction", "workload", "satisfaction_load_ratio"),
    ]
    for cat_a, cat_b, feat_name in pairs:
        a = _get_col(df, sem_map, cat_a)
        b = _get_col(df, sem_map, cat_b)
        if a is None or b is None:
            continue
        try:
            denom = b.replace(0, np.nan)
            df[feat_name] = _clamp((a / denom).clip(-10, 10).fillna(0))
            manifest.features_added.append(feat_name)
        except Exception as e:
            manifest.features_failed.append(f"{feat_name}: {e}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# LAYER B — HR Constructs
# ─────────────────────────────────────────────────────────────────────────────

def _layer_b_hr_constructs(df: pd.DataFrame, sem_map: SemanticMap,
                             manifest: FeatureManifest) -> pd.DataFrame:
    """Core HR psychological and risk constructs."""

    def _add(name: str, formula_fn, is_construct: bool = True):
        try:
            result = formula_fn()
            if result is not None:
                df[name] = _clamp(_norm(result.fillna(result.median())))
                manifest.features_added.append(name)
                manifest.specs_applied.append(FeatureSpec(
                    name=name, formula="computed", layer="B",
                    requires=[], is_construct=is_construct,
                ))
        except Exception as e:
            manifest.features_failed.append(f"{name}: {e}")

    ot  = _get_col(df, sem_map, "overtime")
    wl  = _get_col(df, sem_map, "workload")
    sat = _get_col(df, sem_map, "satisfaction")
    eng = _get_col(df, sem_map, "engagement")
    bur = _get_col(df, sem_map, "burnout")
    perf = _get_col(df, sem_map, "performance")
    sal  = _get_col(df, sem_map, "salary")
    ten  = _get_col(df, sem_map, "tenure")
    prom = _get_col(df, sem_map, "promotion")
    mgr  = _get_col(df, sem_map, "manager_quality")
    abs_ = _get_col(df, sem_map, "absence")
    dist = _get_col(df, sem_map, "distance")
    age  = _get_col(df, sem_map, "age")
    trn  = _get_col(df, sem_map, "training")

    # Burnout Risk Composite: overtime + workload + (1 - satisfaction)
    _add("BurnoutRiskComposite", lambda: (
        _norm(ot.fillna(0)) * 0.40
        + _norm(wl.fillna(0)) * 0.35
        + (1 - _norm(sat.fillna(sat.median()))) * 0.25
    ) if ot is not None and wl is not None and sat is not None else None)

    # Satisfaction Index: satisfaction + engagement composite
    _add("SatisfactionIndex", lambda: (
        _norm(sat.fillna(0)) * 0.55 + _norm(eng.fillna(0)) * 0.45
    ) if sat is not None and eng is not None else None)

    # Engagement Score (single-source if only one available)
    if eng is not None and "SatisfactionIndex" not in df.columns:
        _add("EngagementScore", lambda: _norm(eng.fillna(0)))

    # Retention Risk: composite from multiple risk signals
    parts = []
    weights = []
    if bur is not None:  parts.append(_norm(bur.fillna(0)));  weights.append(0.25)
    if sat is not None:  parts.append(1-_norm(sat.fillna(0))); weights.append(0.20)
    if prom is not None: parts.append(_norm(prom.fillna(0)));  weights.append(0.20)
    if ot is not None:   parts.append(_norm(ot.fillna(0)));    weights.append(0.15)
    if mgr is not None:  parts.append(1-_norm(mgr.fillna(0))); weights.append(0.20)
    if len(parts) >= 3:
        w_sum = sum(weights[:len(parts)])
        _add("RetentionRisk", lambda: sum(p*w for p, w in zip(parts, weights)) / w_sum)

    # Career Progression Score
    _add("CareerProgressionScore", lambda: (
        _norm(perf.fillna(0)) * 0.40
        + (1 - _norm(prom.fillna(0))) * 0.35    # years since last promo (inverted)
        + _norm(trn.fillna(0)) * 0.25
    ) if perf is not None and prom is not None else None)

    # Compensation Equity (salary relative to tenure)
    _add("CompensationEquity", lambda: (
        _norm(sal.fillna(0)) / (_norm(ten.fillna(0)) + 0.1)
    ) if sal is not None and ten is not None else None)

    # Work-Life Balance Risk
    _add("WorkLifeBalanceRisk", lambda: (
        _norm(ot.fillna(0)) * 0.50
        + _norm(dist.fillna(0)) * 0.30
        + _norm(wl.fillna(0)) * 0.20
    ) if ot is not None and dist is not None else None)

    # Managerial Support Index
    _add("ManagerialSupportIndex", lambda: _norm(mgr.fillna(0))
         if mgr is not None else None)

    # Employee Stability Risk: tenure + age proxy
    _add("EmployeeStabilityRisk", lambda: (
        (1 - _norm(ten.fillna(0))) * 0.60
        + (1 - _norm(age.fillna(0))) * 0.40
    ) if ten is not None and age is not None else None)

    # Absenteeism Pressure Index
    _add("AbsenteeismPressureIndex", lambda: _norm(abs_.fillna(0))
         if abs_ is not None else None)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# LAYER C — Psychological Survey Constructs
# ─────────────────────────────────────────────────────────────────────────────

def _layer_c_psychological(df: pd.DataFrame, sem_map: SemanticMap,
                             manifest: FeatureManifest) -> pd.DataFrame:
    """
    When dataset contains psychological/survey columns (Likert), aggregate
    them into latent construct scores using JD-R / COR theory principles.
    """
    psych_cols = sem_map.get("psychological_score")
    if len(psych_cols) < 3:
        return df

    numeric_psych = [c for c in psych_cols if pd.api.types.is_numeric_dtype(df.get(c, pd.Series()))]
    if len(numeric_psych) < 2:
        return df

    try:
        psych_df = df[numeric_psych].apply(pd.to_numeric, errors="coerce")

        # Overall Psychological Wellbeing Score
        df["PsychologicalWellbeingScore"] = _clamp(_norm(psych_df.mean(axis=1)))
        manifest.features_added.append("PsychologicalWellbeingScore")

        # Within-person variability (intra-individual inconsistency signal)
        df["PsychologicalVariabilityIndex"] = _clamp(_norm(psych_df.std(axis=1).fillna(0)))
        manifest.features_added.append("PsychologicalVariabilityIndex")

        # Positive affect proxy: columns where higher = better
        if len(numeric_psych) >= 4:
            top_half = numeric_psych[:len(numeric_psych)//2]
            bot_half = numeric_psych[len(numeric_psych)//2:]
            df["PositiveAffectIndex"] = _clamp(_norm(df[top_half].mean(axis=1)))
            df["NegativeAffectIndex"] = _clamp(1 - _norm(df[bot_half].mean(axis=1)))
            manifest.features_added += ["PositiveAffectIndex", "NegativeAffectIndex"]

    except Exception as e:
        manifest.features_failed.append(f"psychological_constructs: {e}")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# LAYER D — Temporal / Tenure Features
# ─────────────────────────────────────────────────────────────────────────────

def _layer_d_temporal(df: pd.DataFrame, sem_map: SemanticMap,
                       manifest: FeatureManifest) -> pd.DataFrame:
    ten  = _get_col(df, sem_map, "tenure")
    age  = _get_col(df, sem_map, "age")
    prom = _get_col(df, sem_map, "promotion")
    rc   = _get_col(df, sem_map, "role_change")

    if ten is not None:
        try:
            bins = [0, 1, 3, 5, 10, 20, 100]
            labels = [0, 1, 2, 3, 4, 5]
            df["TenureBucket"] = pd.cut(ten, bins=bins, labels=labels, right=True).astype(float)
            manifest.features_added.append("TenureBucket")
        except Exception as e:
            manifest.features_failed.append(f"TenureBucket: {e}")

    if age is not None and ten is not None:
        try:
            # Implied career-start age
            df["CareerStartAge"] = _clamp(_norm((age - ten).clip(16, 40)))
            manifest.features_added.append("CareerStartAge")
        except Exception as e:
            manifest.features_failed.append(f"CareerStartAge: {e}")

    if prom is not None and ten is not None:
        try:
            # Stagnation: promotion gap relative to tenure
            df["PromotionStagnationRatio"] = _clamp(_norm(prom / (ten + 1)))
            manifest.features_added.append("PromotionStagnationRatio")
        except Exception as e:
            manifest.features_failed.append(f"PromotionStagnationRatio: {e}")

    if rc is not None and ten is not None:
        try:
            # Career velocity: job changes per year of total tenure
            df["CareerVelocity"] = _clamp(_norm(rc / (ten + 1)))
            manifest.features_added.append("CareerVelocity")
        except Exception as e:
            manifest.features_failed.append(f"CareerVelocity: {e}")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# LAYER E — Organizational Stress Features
# ─────────────────────────────────────────────────────────────────────────────

def _layer_e_organizational(df: pd.DataFrame, sem_map: SemanticMap,
                              manifest: FeatureManifest) -> pd.DataFrame:
    wl   = _get_col(df, sem_map, "workload")
    ts   = _get_col(df, sem_map, "team_size")
    mgr  = _get_col(df, sem_map, "manager_quality")
    sal  = _get_col(df, sem_map, "salary")
    perf = _get_col(df, sem_map, "performance")
    ot   = _get_col(df, sem_map, "overtime")
    abs_ = _get_col(df, sem_map, "absence")

    if wl is not None and ts is not None:
        try:
            df["WorkloadPerHeadcount"] = _clamp(_norm(wl / (ts + 1)))
            manifest.features_added.append("WorkloadPerHeadcount")
        except Exception as e:
            manifest.features_failed.append(f"WorkloadPerHeadcount: {e}")

    if sal is not None and perf is not None:
        try:
            df["CompensationEfficiencyGap"] = _clamp(_norm(
                _norm(sal) - _norm(perf)
            ))
            manifest.features_added.append("CompensationEfficiencyGap")
        except Exception as e:
            manifest.features_failed.append(f"CompensationEfficiencyGap: {e}")

    if abs_ is not None and ot is not None:
        try:
            # High absence + high overtime → presenteeism / burnout signal
            df["PresenteeismSignal"] = _clamp(_norm(
                _norm(abs_) * 0.50 + _norm(ot) * 0.50
            ))
            manifest.features_added.append("PresenteeismSignal")
        except Exception as e:
            manifest.features_failed.append(f"PresenteeismSignal: {e}")

    if mgr is not None and ts is not None:
        try:
            df["ManagerialStrainIndex"] = _clamp(_norm(
                (1 - _norm(mgr)) * 0.60 + _norm(ts) * 0.40
            ))
            manifest.features_added.append("ManagerialStrainIndex")
        except Exception as e:
            manifest.features_failed.append(f"ManagerialStrainIndex: {e}")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FEATURE FACTORY
# ─────────────────────────────────────────────────────────────────────────────

class FeatureFactory:
    """
    Adaptively engineers features based on detected dataset type and available columns.

    Usage
    -----
    factory = FeatureFactory()
    df_enriched, manifest = factory.engineer(df_clean, sem_map, dataset_type)
    """

    def engineer(self,
                 df: pd.DataFrame,
                 sem_map: SemanticMap,
                 dataset_type: str = "unknown",
                 target_col: Optional[str] = None) -> Tuple[pd.DataFrame, FeatureManifest]:
        df      = df.copy()
        manifest = FeatureManifest(n_original=len(df.columns))

        # ── Scientific Feature Mode Gate ──────────────────────────────────────
        # Layer B (HR constructs) and Layer C (psychological) are DISABLED in
        # theory_grounded mode. They use wrong formulas, normalization before
        # computation, and invented non-paper constructs. The Phase 2
        # TheoryGroundedConstructEngine must run BEFORE this method and add
        # valid constructs to df before feature_factory is called.
        _run_legacy = _LEGACY_MODE_ACTIVE

        if not _run_legacy:
            manifest.legacy_constructs_disabled = list(LEGACY_DISABLED_CONSTRUCTS)
            logger.info(
                "FeatureFactory [%s]: Layer B (HR constructs) and Layer C (psychological) "
                "are DISABLED. %d legacy constructs quarantined. "
                "TheoryGroundedConstructEngine is the active construct source.",
                SCIENTIFIC_FEATURE_MODE,
                len(LEGACY_DISABLED_CONSTRUCTS),
            )
        else:
            logger.warning(
                "FeatureFactory [LEGACY_FOR_DEBUG_ONLY]: Layer B and C are ACTIVE. "
                "Constructs use scientifically invalid formulas. "
                "DO NOT use this output for reports, scoring, or any production purpose."
            )

        # Always run universal layers (safe — no theory formula claims)
        df = _layer_a_interactions(df, sem_map, manifest)
        df = _layer_d_temporal(df, sem_map, manifest)

        # HR-specific layers — gated by scientific mode
        if dataset_type in ("hr_attrition", "hr_engagement", "hr_performance",
                             "burnout_survey", "mixed", "unknown"):
            if _run_legacy:
                df = _layer_b_hr_constructs(df, sem_map, manifest)
            df = _layer_e_organizational(df, sem_map, manifest)

        # Psychological / survey layers — gated by scientific mode
        if dataset_type in ("psychological_survey", "burnout_survey",
                             "hr_engagement", "mixed"):
            if _run_legacy:
                df = _layer_c_psychological(df, sem_map, manifest)

        # Remove any legacy constructs that leaked into df from prior runs
        if not _run_legacy:
            for col in LEGACY_DISABLED_CONSTRUCTS:
                if col in df.columns:
                    df = df.drop(columns=[col])
                    logger.warning(
                        "FeatureFactory: removed legacy construct '%s' from df "
                        "(was pre-computed; blocked by SCIENTIFIC_FEATURE_MODE=%s)",
                        col, SCIENTIFIC_FEATURE_MODE,
                    )

        # Remove target from feature list
        if target_col and target_col in df.columns:
            _ = df[target_col]  # keep it present, just note it's not a feature

        manifest.n_final = len(df.columns)
        logger.info(
            "FeatureFactory: added %d features, failed %d, legacy_disabled=%d, total cols=%d",
            len(manifest.features_added), len(manifest.features_failed),
            len(manifest.legacy_constructs_disabled), manifest.n_final,
        )
        return df, manifest
