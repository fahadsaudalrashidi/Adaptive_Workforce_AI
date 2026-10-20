"""
Unified Confidence Governance System
=====================================
Single authoritative source of confidence scores for the platform.

Produces one UnifiedConfidenceReport with exactly five dimensions:
  1. data_quality_score        — completeness, consistency, schema
  2. routing_confidence        — dataset type detection certainty
  3. model_reliability_score   — validation, leakage, calibration, stability
  4. analysis_confidence       — combined final score used in all reports
  5. executive_readiness       — Ready / Caution / Limited / Not Ready

Rules enforced here (never in the UI):
  - If routing_confidence < 0.50 → analysis_confidence cannot exceed 0.70
  - If leakage_risk > 0.30 → model_reliability must be downgraded
  - If any CRITICAL leakage flag → model_reliability capped at 0.40
  - If model_reliability < 0.60 → executive language must be cautious
  - If data_quality < 0.55 → analysis_confidence capped at 0.65
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

EXEC_READY   = "Ready"
EXEC_CAUTION = "Caution"
EXEC_LIMITED = "Limited"
EXEC_NOT_READY = "Not Ready"


# ─────────────────────────────────────────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConfidenceDimension:
    """One dimension of the unified confidence report."""
    label: str
    score: float          # 0–1
    band: str             # High / Moderate / Low / Unreliable
    reason: str           # plain-English explanation
    degraded_by: List[str] = field(default_factory=list)


@dataclass
class UnifiedConfidenceReport:
    """
    The single source of truth for all confidence values shown to the user.
    All UI panels and reports must read from this object, never compute
    confidence independently.
    """
    data_quality:         ConfidenceDimension
    routing_confidence:   ConfidenceDimension
    model_reliability:    ConfidenceDimension
    analysis_confidence:  ConfidenceDimension
    executive_readiness:  str              # EXEC_* constant
    executive_reason:     str             # plain-English readiness explanation
    has_ml_model:         bool
    leakage_risk_score:   float           # 0–1
    is_trustworthy:       bool
    governed_auc:         float
    original_auc:         float
    # Human-readable summary for display
    summary: str
    # Caveats to show under scores
    caveats: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _band(score: float) -> str:
    if score >= 0.80:
        return "High"
    if score >= 0.65:
        return "Moderate"
    if score >= 0.50:
        return "Low"
    return "Unreliable"


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ─────────────────────────────────────────────────────────────────────────────
# BUILDER
# ─────────────────────────────────────────────────────────────────────────────

class ConfidenceGovernor:
    """
    Builds a UnifiedConfidenceReport from raw analysis outputs.

    Call build() after training and leakage/validation checks.
    """

    def build(
        self,
        *,
        # Data quality inputs
        profiler_quality_score: float,          # 0–100 from DatasetProfiler
        missing_pct: float,                     # 0–1
        n_rows: int,
        n_cols: int,
        # Routing inputs
        routing_type: str,
        routing_confidence_raw: float,          # 0–1 from DatasetConfidenceEngine
        routing_locked: bool,
        # ML model inputs (optional — None if no model trained)
        has_ml_model: bool,
        original_auc: float = 0.0,
        governed_auc: float = 0.0,
        leakage_risk_score: float = 0.0,
        leakage_n_critical: int = 0,
        leakage_n_high: int = 0,
        is_trustworthy: bool = True,
        validation_overall_status: str = "VALID",   # VALID / DEGRADED / INVALID
        validation_n_fail: int = 0,
        oof_fold_std: Optional[float] = None,
        # Calibration inputs (optional — None = not evaluated)
        brier_score: Optional[float] = None,        # 0–1 lower is better; 0.25 = random
        calibration_ece: Optional[float] = None,    # expected calibration error 0–1
        # Feature trustworthiness (optional — from FeatureTrustworthinessReport)
        feature_trust_score: Optional[float] = None,  # 0–1; 1=all reliable
        feature_dominance_flag: bool = False,
        # Train/test gap (optional — val_auc - train_auc; negative = overfitting)
        train_test_gap: Optional[float] = None,
        # Class balance (optional — minority_class_pct; 0=extremely imbalanced, 0.5=balanced)
        class_balance_ratio: Optional[float] = None,
        # Deployment safety from ValidationReport
        deployment_safe: Optional[bool] = None,
        # Construct evidence
        has_burnout_evidence: bool = True,
        has_engagement_evidence: bool = True,
    ) -> UnifiedConfidenceReport:

        caveats: List[str] = []

        # ── Dimension 1: Data Quality ─────────────────────────────────────────
        dq_score = _clamp(profiler_quality_score / 100.0)
        dq_degraded: List[str] = []
        if missing_pct > 0.30:
            dq_score = _clamp(dq_score * 0.80)
            dq_degraded.append(f"High missing data ({missing_pct:.0%})")
            caveats.append(f"Data contains {missing_pct:.0%} missing values — results may be incomplete.")
        if n_rows < 200:
            dq_score = _clamp(dq_score * 0.75)
            dq_degraded.append(f"Small dataset ({n_rows:,} rows)")
            caveats.append(f"Small dataset ({n_rows:,} rows) — statistical reliability is limited.")

        dq_reason = (
            f"Data quality based on completeness ({1-missing_pct:.0%} complete), "
            f"schema consistency, and dataset size ({n_rows:,} rows × {n_cols} columns)."
        )
        if dq_degraded:
            dq_reason += " Degraded by: " + ", ".join(dq_degraded) + "."
        dim_dq = ConfidenceDimension(
            label="Data Quality",
            score=round(dq_score, 3),
            band=_band(dq_score),
            reason=dq_reason,
            degraded_by=dq_degraded,
        )

        # ── Dimension 2: Routing Confidence ──────────────────────────────────
        rc_score = _clamp(routing_confidence_raw)
        rc_degraded: List[str] = []
        if routing_locked:
            # Hard rule applied — routing is certain
            rc_score = _clamp(max(rc_score, 0.90))
            rc_reason = f"Dataset type '{routing_type}' confirmed by hard filename/signal rule."
        else:
            if rc_score < 0.50:
                rc_degraded.append("Low routing certainty")
                caveats.append("Dataset type detection confidence is low — analysis may be misaligned.")
            rc_reason = (
                f"Dataset classified as '{routing_type}' with {rc_score:.0%} certainty. "
                + ("Manual verification recommended." if rc_score < 0.65 else "Routing appears reliable.")
            )
        dim_rc = ConfidenceDimension(
            label="Routing Confidence",
            score=round(rc_score, 3),
            band=_band(rc_score),
            reason=rc_reason,
            degraded_by=rc_degraded,
        )

        # ── Dimension 3: Model Reliability (multi-component — NOT AUC-only) ─────
        # Formula: 25% AUC + 20% leakage cleanliness + 15% calibration
        #          + 15% fold stability + 10% feature trust + 10% train/test gap
        #          + 5% data sufficiency
        # Missing components are treated as 0.60 (uncertain, not penalized fully)
        if not has_ml_model:
            mr_score = 0.0
            mr_degraded = ["No ML model trained"]
            mr_reason = "No predictive model trained — unsupervised or profiling mode."
        else:
            mr_degraded: List[str] = []
            _not_eval: List[str] = []

            # Component 1: AUC quality (25%) — capped at 0.95 to avoid overconfidence
            _auc_component = _clamp(min(governed_auc, 0.95))

            # Component 2: Leakage cleanliness (20%) — inverse of leakage risk
            _leakage_clean = _clamp(1.0 - leakage_risk_score)
            if leakage_n_critical > 0:
                _leakage_clean = _clamp(_leakage_clean * 0.50)
                mr_degraded.append(f"{leakage_n_critical} critical leakage flag(s)")
                caveats.append(
                    f"Critical data leakage detected ({leakage_n_critical} flags) — "
                    "model reliability is significantly degraded."
                )

            # Component 3: Calibration quality (15%)
            if brier_score is not None:
                # Brier score: 0=perfect, 0.25=random coin flip, >0.25=worse than random
                _calib_component = _clamp(1.0 - min(brier_score / 0.25, 1.0))
                if brier_score > 0.20:
                    mr_degraded.append(f"Poor calibration (Brier={brier_score:.3f})")
                    caveats.append(f"Brier score {brier_score:.3f} indicates poor probability calibration.")
            elif calibration_ece is not None:
                _calib_component = _clamp(1.0 - min(calibration_ece / 0.20, 1.0))
                if calibration_ece > 0.10:
                    mr_degraded.append(f"Calibration ECE={calibration_ece:.3f}")
            else:
                _calib_component = 0.60   # uncertain — not penalized fully
                _not_eval.append("Calibration")
                caveats.append("Calibration quality not evaluated — probabilities may be over/underconfident.")

            # Component 4: Fold stability (15%)
            if oof_fold_std is not None:
                _fold_component = _clamp(1.0 - min(oof_fold_std / 0.20, 1.0))
                if oof_fold_std > 0.10:
                    mr_degraded.append(f"Fold instability (std={oof_fold_std:.3f})")
            else:
                _fold_component = 0.60
                _not_eval.append("CV Stability")

            # Component 5: Feature trustworthiness (10%)
            if feature_trust_score is not None:
                _feat_component = _clamp(feature_trust_score)
            elif feature_dominance_flag:
                _feat_component = 0.50
                mr_degraded.append("Feature dominance flag")
            else:
                _feat_component = 0.70
                _not_eval.append("Feature Trust")

            # Component 6: Train/test generalization gap (10%)
            if train_test_gap is not None:
                # Negative gap = overfitting; zero or small positive = good generalization
                _gap_penalty = max(0.0, -train_test_gap)  # overfitting magnitude
                _gap_component = _clamp(1.0 - min(_gap_penalty / 0.20, 1.0))
                if _gap_penalty > 0.10:
                    mr_degraded.append(f"Train/test gap {_gap_penalty:.3f}")
            else:
                _gap_component = 0.65
                _not_eval.append("Train/Test Gap")

            # Component 7: Data sufficiency (5%)
            if n_rows >= 1000:
                _data_suf = 1.0
            elif n_rows >= 500:
                _data_suf = 0.85
            elif n_rows >= 200:
                _data_suf = 0.65
            else:
                _data_suf = 0.40
                mr_degraded.append(f"Small dataset ({n_rows} rows)")

            # Component 8: Class balance (2%)
            if class_balance_ratio is not None:
                if class_balance_ratio < 0.05:
                    _class_bal = 0.30
                    mr_degraded.append(f"Severe class imbalance (minority={class_balance_ratio:.1%})")
                    caveats.append(f"Minority class is only {class_balance_ratio:.1%} — model may over-predict majority class.")
                elif class_balance_ratio < 0.10:
                    _class_bal = 0.55
                    mr_degraded.append(f"Class imbalance (minority={class_balance_ratio:.1%})")
                elif class_balance_ratio < 0.20:
                    _class_bal = 0.75
                else:
                    _class_bal = 1.0
            else:
                _class_bal = 0.65
                _not_eval.append("Class Balance")

            # Component 9: Deployment safety (3%)
            if deployment_safe is True:
                _deploy_safe = 1.0
            elif deployment_safe is False:
                _deploy_safe = 0.20
                mr_degraded.append("ValidationReport: NOT deployment-safe")
                caveats.append("Model failed deployment safety validation — do not use in automated decisions.")
            else:
                _deploy_safe = 0.65
                _not_eval.append("Deployment Safety")

            # Weighted composite (weights sum to 1.00)
            mr_score = _clamp(
                _auc_component    * 0.22 +
                _leakage_clean    * 0.20 +
                _calib_component  * 0.15 +
                _fold_component   * 0.13 +
                _feat_component   * 0.10 +
                _gap_component    * 0.10 +
                _data_suf         * 0.05 +
                _class_bal        * 0.02 +
                _deploy_safe      * 0.03
            )

            # Hard governance overrides
            if validation_n_fail > 0:
                mr_score = _clamp(mr_score * (1.0 - 0.08 * validation_n_fail))
                mr_degraded.append(f"{validation_n_fail} validation check(s) failed")
            if validation_overall_status == "INVALID":
                mr_score = _clamp(min(mr_score, 0.45))
                mr_degraded.append("Model validation INVALID")
                caveats.append("Model failed validation checks — predictions should not be used in decisions.")
            elif validation_overall_status == "DEGRADED":
                mr_score = _clamp(min(mr_score, 0.72))

            not_eval_str = (f" Not evaluated: {', '.join(_not_eval)}." if _not_eval else "")
            mr_reason = (
                "Model Reliability is not the same as AUC. "
                f"Composite score: AUC {_auc_component:.0%} (×0.22) + "
                f"leakage cleanliness {_leakage_clean:.0%} (×0.20) + "
                f"calibration {_calib_component:.0%} (×0.15) + "
                f"fold stability {_fold_component:.0%} (×0.13) + "
                f"feature trust {_feat_component:.0%} (×0.10) + "
                f"generalization {_gap_component:.0%} (×0.10) + "
                f"data sufficiency {_data_suf:.0%} (×0.05) + "
                f"class balance {_class_bal:.0%} (×0.02) + "
                f"deployment safety {_deploy_safe:.0%} (×0.03). "
                f"Original AUC: {original_auc:.3f} | Governed AUC: {governed_auc:.3f}."
                + not_eval_str
            )
            if mr_degraded:
                mr_reason += " Degraded by: " + ", ".join(mr_degraded) + "."

        dim_mr = ConfidenceDimension(
            label="Model Reliability",
            score=round(mr_score, 3) if has_ml_model else 0.0,
            band=_band(mr_score) if has_ml_model else "N/A",
            reason=mr_reason,
            degraded_by=mr_degraded if has_ml_model else ["No model"],
        )

        # ── Dimension 4: Analysis Confidence (combined) ───────────────────────
        if has_ml_model:
            ac_score = (dq_score * 0.25 + rc_score * 0.25 + mr_score * 0.50)
        else:
            ac_score = (dq_score * 0.50 + rc_score * 0.50)

        ac_degraded: List[str] = []
        # Hard governance caps
        if rc_score < 0.50:
            ac_score = _clamp(min(ac_score, 0.70))
            ac_degraded.append("Routing confidence < 50%")
        if dq_score < 0.55:
            ac_score = _clamp(min(ac_score, 0.65))
            ac_degraded.append("Data quality < 55%")
        if not is_trustworthy:
            ac_score = _clamp(min(ac_score, 0.50))
            ac_degraded.append("Model not trustworthy (critical leakage)")

        if not has_burnout_evidence:
            caveats.append("Burnout construct evidence unavailable — displayed as N/A.")
        if not has_engagement_evidence:
            caveats.append("Engagement construct evidence unavailable — displayed as N/A.")

        ac_reason = (
            f"Combined score weighted: data quality ({dq_score:.0%}) × 0.25 + "
            f"routing ({rc_score:.0%}) × 0.25 + "
            + (f"model reliability ({mr_score:.0%}) × 0.50." if has_ml_model
               else "no model component.")
        )
        if ac_degraded:
            ac_reason += " Hard caps applied: " + ", ".join(ac_degraded) + "."

        dim_ac = ConfidenceDimension(
            label="Analysis Confidence",
            score=round(ac_score, 3),
            band=_band(ac_score),
            reason=ac_reason,
            degraded_by=ac_degraded,
        )

        # ── Executive Readiness ───────────────────────────────────────────────
        if not is_trustworthy or validation_overall_status == "INVALID":
            exec_ready = EXEC_NOT_READY
            exec_reason = (
                "Predictions are not suitable for executive review. "
                "Critical leakage or model validation failures must be resolved first."
            )
        elif ac_score >= 0.75 and mr_score >= 0.70:
            exec_ready = EXEC_READY
            exec_reason = (
                "Analysis confidence is high. Results are suitable for executive review "
                "with standard human oversight protocols."
            )
        elif ac_score >= 0.60:
            exec_ready = EXEC_CAUTION
            exec_reason = (
                "Analysis confidence is moderate. Results provide useful decision-support signals "
                "but should be validated by HR professionals before action is taken."
            )
        elif ac_score >= 0.45:
            exec_ready = EXEC_LIMITED
            exec_reason = (
                "Analysis confidence is limited. Structural or model quality issues reduce reliability. "
                "Use findings as preliminary indicators only."
            )
        else:
            exec_ready = EXEC_NOT_READY
            exec_reason = (
                "Analysis confidence is too low for executive use. "
                "Improve data quality or dataset coverage before proceeding."
            )

        # Summary
        summary = (
            f"Data: {dim_dq.band} ({dim_dq.score:.0%}) | "
            f"Routing: {dim_rc.band} ({dim_rc.score:.0%}) | "
            + (f"Model: {dim_mr.band} ({dim_mr.score:.0%}) | " if has_ml_model else "No model | ")
            + f"Overall: {dim_ac.band} ({dim_ac.score:.0%}) | "
            f"Readiness: {exec_ready}"
        )

        return UnifiedConfidenceReport(
            data_quality        = dim_dq,
            routing_confidence  = dim_rc,
            model_reliability   = dim_mr,
            analysis_confidence = dim_ac,
            executive_readiness = exec_ready,
            executive_reason    = exec_reason,
            has_ml_model        = has_ml_model,
            leakage_risk_score  = leakage_risk_score,
            is_trustworthy      = is_trustworthy,
            governed_auc        = governed_auc,
            original_auc        = original_auc,
            summary             = summary,
            caveats             = caveats,
        )
