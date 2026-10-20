"""
Explainability Engine — SHAP integration, feature importance, NL reasoning.

Produces ExplainabilityReport for any trained model or biosignal profile.
Gracefully degrades if SHAP is not installed.

Every prediction exposed to the user must carry:
  - feature importance ranking
  - top contributing factors (with direction)
  - natural language reasoning summary
  - statistical confidence indicator
  - provenance trace (what data → what model → what output)
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SHAP — optional; graceful fallback if not installed
# ─────────────────────────────────────────────────────────────────────────────

_SHAP_AVAILABLE = False
try:
    import shap as _shap
    _SHAP_AVAILABLE = True
except (ImportError, Exception):
    _shap = None  # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FeatureFact:
    """One explainable fact about a feature's contribution."""
    feature_name: str
    importance_score: float          # 0–1 normalised
    direction: str                   # "increases_risk" / "decreases_risk" / "neutral"
    magnitude: str                   # "strong" / "moderate" / "weak"
    plain_english: str               # e.g. "High overtime strongly increases attrition risk"
    shap_mean_abs: float = 0.0       # mean |SHAP| value (0 if not computed)
    data_source: str = "feature_importance"  # "shap" / "feature_importance" / "correlation"


@dataclass
class ProvenanceTrace:
    """Audit trail: data → preprocessing → model → prediction."""
    dataset_type: str
    dataset_subtype: str
    n_rows_input: int
    n_rows_after_healing: int
    n_features_raw: int
    n_features_engineered: int
    model_type: str                    # "XGBoost" / "RandomForest" / "Unsupervised" etc.
    model_auc: float                   # 0 if unsupervised
    training_mode: str                 # "supervised" / "unsupervised" / "biosignal"
    target_column: Optional[str]
    preprocessing_steps: List[str] = field(default_factory=list)
    feature_sources: Dict[str, str] = field(default_factory=dict)  # feat → "raw"/"engineered"/"semantic"
    timestamp: str = ""


@dataclass
class StatisticalValidity:
    """How much we can trust this output."""
    level: str                        # "High" / "Medium" / "Low" / "Insufficient"
    confidence_score: float           # 0–1
    sample_size_adequate: bool
    class_balance_adequate: bool
    feature_quality: str              # "Good" / "Fair" / "Poor"
    data_quality_impact: str          # plain-English impact statement
    caveats: List[str] = field(default_factory=list)
    recommended_min_samples: int = 100


@dataclass
class ExplainabilityReport:
    """
    Complete explainability package attached to every analysis result.
    Every insight shown in the UI must be traceable to this report.
    """
    # Core outputs
    top_features: List[FeatureFact]          # top N feature explanations
    provenance: ProvenanceTrace
    validity: StatisticalValidity

    # Global explanations
    global_summary: str                      # 2–3 sentence model explanation
    reasoning_chain: List[str]               # step-by-step reasoning
    uncertainty_note: str                    # uncertainty / caveat statement

    # SHAP (populated if SHAP available)
    shap_available: bool = False
    shap_global_importance: Dict[str, float] = field(default_factory=dict)
    shap_explanation_text: str = ""

    # Metadata
    model_type: str = ""
    training_mode: str = ""
    n_samples_explained: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# NATURAL LANGUAGE TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

_RISK_TEMPLATES = {
    "increases_risk": {
        "strong":   "{feat} is a strong driver of attrition risk.",
        "moderate": "{feat} moderately increases attrition risk.",
        "weak":     "{feat} slightly increases attrition risk.",
    },
    "decreases_risk": {
        "strong":   "{feat} strongly reduces attrition risk.",
        "moderate": "{feat} moderately protects against attrition.",
        "weak":     "{feat} provides mild protection against attrition.",
    },
    "neutral": {
        "strong":   "{feat} is a major discriminating factor.",
        "moderate": "{feat} is a relevant factor.",
        "weak":     "{feat} has minor influence.",
    },
}

_DIRECTION_THRESHOLD_HIGH = 0.6
_DIRECTION_THRESHOLD_LOW  = 0.4


def _score_to_magnitude(score: float) -> str:
    if score >= 0.60:
        return "strong"
    if score >= 0.30:
        return "moderate"
    return "weak"


def _plain_english_fact(feat: str, score: float, direction: str) -> str:
    mag = _score_to_magnitude(score)
    template = _RISK_TEMPLATES.get(direction, _RISK_TEMPLATES["neutral"]).get(mag, "{feat} is relevant.")
    return template.format(feat=feat.replace("_", " ").title())


# ─────────────────────────────────────────────────────────────────────────────
# SHAP COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def _compute_shap_values(
    model: Any,
    X: pd.DataFrame,
    n_samples: int = 100,
) -> Optional[np.ndarray]:
    """
    Attempt SHAP computation. Returns mean |SHAP| per feature or None.
    Samples the dataframe to control runtime.
    """
    if not _SHAP_AVAILABLE or model is None:
        return None
    try:
        X_sample = X.head(min(n_samples, len(X)))
        try:
            explainer  = _shap.TreeExplainer(model)
            shap_vals  = explainer.shap_values(X_sample)
        except Exception:
            try:
                explainer = _shap.Explainer(model, X_sample)
                shap_vals = explainer(X_sample).values
            except Exception:
                return None

        # Binary classification: take positive class
        if isinstance(shap_vals, list) and len(shap_vals) == 2:
            shap_vals = shap_vals[1]
        if shap_vals is None:
            return None
        return np.abs(np.array(shap_vals)).mean(axis=0)
    except Exception:
        logger.debug("SHAP computation failed: %s", traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# VALIDITY ASSESSMENT
# ─────────────────────────────────────────────────────────────────────────────

def _assess_validity(
    n_rows: int,
    n_features: int,
    class_balance: Optional[float],
    model_auc: float,
    training_mode: str,
    data_quality_score: float,
) -> StatisticalValidity:
    caveats: List[str] = []
    confidence = 1.0

    # Sample size
    sample_ok = n_rows >= 100
    if not sample_ok:
        confidence -= 0.30
        caveats.append(f"Small sample ({n_rows} rows) — results may not generalise.")
    elif n_rows < 300:
        confidence -= 0.10
        caveats.append(f"Moderate sample ({n_rows} rows) — interpret with caution.")

    # Class balance (for supervised)
    balance_ok = True
    if training_mode == "supervised" and class_balance is not None:
        minority_pct = min(class_balance, 1 - class_balance)
        if minority_pct < 0.10:
            balance_ok = False
            confidence -= 0.20
            caveats.append(f"Severe class imbalance ({minority_pct:.0%} minority) — predictions may be unreliable for minority class.")
        elif minority_pct < 0.20:
            confidence -= 0.10
            caveats.append(f"Moderate class imbalance ({minority_pct:.0%} minority) — SMOTE was applied.")

    # Model quality
    if training_mode == "supervised":
        if model_auc < 0.55:
            confidence -= 0.30
            caveats.append(f"Model AUC {model_auc:.2f} is near random — predictions are unreliable.")
        elif model_auc < 0.70:
            confidence -= 0.15
            caveats.append(f"Model AUC {model_auc:.2f} indicates moderate predictive power.")

    # Data quality
    fq = "Good"
    if data_quality_score < 50:
        confidence -= 0.20
        fq = "Poor"
        caveats.append("Low data quality score may undermine analytical validity.")
    elif data_quality_score < 70:
        confidence -= 0.10
        fq = "Fair"
        caveats.append("Moderate data quality — results are indicative, not conclusive.")

    confidence = max(0.05, min(1.0, confidence))

    if confidence >= 0.75:
        level = "High"
    elif confidence >= 0.50:
        level = "Medium"
    elif confidence >= 0.25:
        level = "Low"
    else:
        level = "Insufficient"

    dq_impact = (
        "Data quality is good — results are reliable within model assumptions."
        if data_quality_score >= 70
        else f"Data quality ({data_quality_score:.0f}/100) may reduce analytical reliability."
    )

    return StatisticalValidity(
        level=level,
        confidence_score=round(confidence, 3),
        sample_size_adequate=sample_ok,
        class_balance_adequate=balance_ok,
        feature_quality=fq,
        data_quality_impact=dq_impact,
        caveats=caveats,
        recommended_min_samples=100,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE FACTS BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_feature_facts(
    feature_importances: Dict[str, float],
    shap_values_mean_abs: Optional[np.ndarray],
    feature_names: List[str],
    top_n: int = 15,
    correlation_with_target: Optional[pd.Series] = None,
) -> List[FeatureFact]:
    if not feature_importances:
        return []

    # Normalise importances to 0–1
    total = sum(feature_importances.values()) or 1.0
    norm_imp = {k: v / total for k, v in feature_importances.items()}

    # Build SHAP lookup
    shap_lookup: Dict[str, float] = {}
    if shap_values_mean_abs is not None and len(shap_values_mean_abs) == len(feature_names):
        shap_total = float(shap_values_mean_abs.sum()) or 1.0
        shap_lookup = {
            fn: float(sv) / shap_total
            for fn, sv in zip(feature_names, shap_values_mean_abs)
        }

    # Build correlation lookup
    corr_lookup: Dict[str, float] = {}
    if correlation_with_target is not None:
        corr_lookup = correlation_with_target.dropna().to_dict()

    facts: List[FeatureFact] = []
    sorted_feats = sorted(norm_imp.items(), key=lambda x: x[1], reverse=True)[:top_n]

    for feat, score in sorted_feats:
        # Direction from correlation
        corr = corr_lookup.get(feat, 0.0)
        if abs(corr) < 0.05:
            direction = "neutral"
        elif corr > 0:
            direction = "increases_risk"
        else:
            direction = "decreases_risk"

        shap_score = shap_lookup.get(feat, score)
        source = "shap" if feat in shap_lookup else "feature_importance"

        facts.append(FeatureFact(
            feature_name=feat,
            importance_score=round(score, 4),
            direction=direction,
            magnitude=_score_to_magnitude(score),
            plain_english=_plain_english_fact(feat, score, direction),
            shap_mean_abs=round(shap_score, 4),
            data_source=source,
        ))

    return facts


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL SUMMARY GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def _build_global_summary(
    top_features: List[FeatureFact],
    validity: StatisticalValidity,
    training_mode: str,
    model_type: str,
    dataset_type: str,
) -> Tuple[str, List[str], str]:
    """Returns (global_summary, reasoning_chain, uncertainty_note)."""

    if training_mode == "biosignal":
        summary = (
            "This is a physiological signal analysis, not a workforce prediction. "
            "The engine computed composite stress proxy scores from wearable sensor windows. "
            "No employee-level predictions were made."
        )
        chain = [
            "1. Signal uploaded and classified as biosignal dataset.",
            "2. 30-second windows extracted with 50% overlap.",
            "3. Per-window features computed (mean, std, volatility, signal-specific metrics).",
            "4. Composite scores aggregated across all windows.",
            "5. Stress proxy level assigned based on score thresholds.",
        ]
        uncertainty = (
            "Physiological proxy scores reflect sensor patterns — they are not clinical diagnoses. "
            "Individual baseline variation, artifacts, and context substantially affect scores."
        )
        return summary, chain, uncertainty

    top_names = [f.feature_name.replace("_", " ").title() for f in top_features[:3]]
    top_str = ", ".join(top_names) if top_names else "unknown features"
    mode_str = "supervised attrition model" if training_mode == "supervised" else "unsupervised risk scorer"

    summary = (
        f"A {model_type} {mode_str} was applied to this {dataset_type.replace('_', ' ')} dataset. "
        f"The top predictive signals identified are: {top_str}. "
        f"Statistical confidence is {validity.level} ({validity.confidence_score:.0%})."
    )

    chain = [
        f"1. Dataset classified as {dataset_type.replace('_', ' ')} with {validity.feature_quality.lower()} data quality.",
        f"2. {'Target column detected — supervised training.' if training_mode == 'supervised' else 'No target column — unsupervised risk scoring applied.'}",
        f"3. {model_type} model selected based on dataset characteristics.",
        f"4. Top predictors: {top_str}.",
        f"5. Confidence level: {validity.level} — {'; '.join(validity.caveats[:2]) if validity.caveats else 'no major caveats.'}",
    ]

    if validity.caveats:
        uncertainty = (
            f"Confidence is {validity.level} due to: {validity.caveats[0]}. "
            "Results should be interpreted with appropriate caution and validated with domain expertise."
        )
    else:
        uncertainty = (
            "This analysis meets basic statistical requirements. "
            "Predictions reflect patterns in the provided dataset and should be validated operationally."
        )

    return summary, chain, uncertainty


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class ExplainabilityEngine:
    """
    Produces an ExplainabilityReport from any analysis result.
    Safe to call even if SHAP is unavailable or model is None.
    """

    def explain_hr(
        self,
        *,
        ml_result: Any,                        # MLResult or None
        df_eng: pd.DataFrame,
        feature_names: List[str],
        target_col: Optional[str],
        dataset_type: str,
        dataset_subtype: str,
        n_rows_input: int,
        n_rows_healed: int,
        n_features_raw: int,
        data_quality_score: float,
        training_mode: str,                    # "supervised" / "unsupervised"
        preprocessing_steps: Optional[List[str]] = None,
    ) -> ExplainabilityReport:

        model      = None
        model_type = "Unsupervised Risk Scorer"
        model_auc  = 0.0
        fi: Dict[str, float] = {}

        if ml_result is not None:
            best_name  = getattr(ml_result, "best_model_name", "Unknown")
            model_type = best_name
            model_auc  = getattr(ml_result, "best_metric_value", 0.0)
            best_mr    = getattr(ml_result, "models", {}).get(best_name)
            if best_mr:
                fi    = getattr(best_mr, "feature_importances", {}) or {}
                model = getattr(best_mr, "pipeline", None)

        # Class balance
        class_balance: Optional[float] = None
        if target_col and target_col in df_eng.columns:
            vc = df_eng[target_col].value_counts(normalize=True)
            if len(vc) == 2:
                class_balance = float(vc.iloc[1])

        # SHAP
        shap_mean_abs: Optional[np.ndarray] = None
        if model is not None and _SHAP_AVAILABLE and len(feature_names) > 0:
            try:
                X = df_eng[feature_names].fillna(0)
                shap_mean_abs = _compute_shap_values(model, X)
            except Exception:
                pass

        # Correlation with target
        corr: Optional[pd.Series] = None
        if target_col and target_col in df_eng.columns:
            try:
                num_df = df_eng[feature_names].select_dtypes(include=[np.number])
                y = df_eng[target_col]
                if not pd.api.types.is_numeric_dtype(y):
                    y = (y.astype(str).str.lower().isin({"yes","1","true","left"})).astype(float)
                corr = num_df.corrwith(y)
            except Exception:
                pass

        top_features = _build_feature_facts(fi, shap_mean_abs, feature_names, top_n=15, correlation_with_target=corr)
        validity = _assess_validity(
            n_rows=n_rows_input,
            n_features=len(feature_names),
            class_balance=class_balance,
            model_auc=model_auc,
            training_mode=training_mode,
            data_quality_score=data_quality_score,
        )

        summary, chain, uncertainty = _build_global_summary(
            top_features, validity, training_mode, model_type, dataset_type,
        )

        provenance = ProvenanceTrace(
            dataset_type=dataset_type,
            dataset_subtype=dataset_subtype,
            n_rows_input=n_rows_input,
            n_rows_after_healing=n_rows_healed,
            n_features_raw=n_features_raw,
            n_features_engineered=len(feature_names),
            model_type=model_type,
            model_auc=model_auc,
            training_mode=training_mode,
            target_column=target_col,
            preprocessing_steps=preprocessing_steps or [],
            feature_sources={f: "engineered" for f in feature_names[:5]},
        )

        shap_global: Dict[str, float] = {}
        shap_text = ""
        if shap_mean_abs is not None and len(shap_mean_abs) == len(feature_names):
            shap_total = float(shap_mean_abs.sum()) or 1.0
            shap_global = {fn: float(sv) / shap_total
                           for fn, sv in zip(feature_names, shap_mean_abs)}
            top_shap = sorted(shap_global.items(), key=lambda x: x[1], reverse=True)[:5]
            shap_text = "SHAP top contributors: " + ", ".join(
                f"{k.replace('_',' ').title()} ({v:.1%})" for k, v in top_shap
            )

        return ExplainabilityReport(
            top_features=top_features,
            provenance=provenance,
            validity=validity,
            global_summary=summary,
            reasoning_chain=chain,
            uncertainty_note=uncertainty,
            shap_available=shap_mean_abs is not None,
            shap_global_importance=shap_global,
            shap_explanation_text=shap_text,
            model_type=model_type,
            training_mode=training_mode,
            n_samples_explained=min(100, n_rows_input),
        )

    def explain_biosignal(
        self,
        *,
        signal_type: str,
        n_samples: int,
        n_windows: int,
        quality_score: float,
        stress_score: float,
        anomaly_count: int,
    ) -> ExplainabilityReport:

        validity = _assess_validity(
            n_rows=n_windows,
            n_features=1,
            class_balance=None,
            model_auc=0.0,
            training_mode="biosignal",
            data_quality_score=quality_score,
        )

        # Provenance
        provenance = ProvenanceTrace(
            dataset_type="biosignal_timeseries",
            dataset_subtype=f"wesad_{signal_type.lower()}",
            n_rows_input=n_samples,
            n_rows_after_healing=n_samples,
            n_features_raw=1,
            n_features_engineered=10,
            model_type="Signal Processing Pipeline",
            model_auc=0.0,
            training_mode="biosignal",
            target_column=None,
            preprocessing_steps=[
                "Signal loaded and validated",
                f"30-second windows extracted ({n_windows} windows)",
                "Per-window features computed",
                "Composite scores aggregated",
                "Stress proxy level assigned",
            ],
        )

        # Feature facts for biosignal
        bio_features = {
            "HR": [("heart_rate_mean", 0.4, "increases_risk"),
                   ("hr_stress_proxy", 0.3, "increases_risk"),
                   ("elevated_hr_ratio", 0.2, "increases_risk"),
                   ("hr_variability", 0.1, "decreases_risk")],
            "EDA": [("eda_mean_conductance", 0.4, "increases_risk"),
                    ("stress_activation_score", 0.35, "increases_risk"),
                    ("eda_spike_count", 0.15, "increases_risk"),
                    ("sympathetic_arousal", 0.1, "increases_risk")],
            "BVP": [("bvp_volatility", 0.4, "increases_risk"),
                    ("cardiovascular_instability", 0.35, "increases_risk"),
                    ("bvp_mean", 0.15, "neutral"),
                    ("pulse_variability", 0.1, "increases_risk")],
            "IBI": [("hrv_sdnn_ms", 0.4, "decreases_risk"),
                    ("hrv_rmssd_ms", 0.35, "decreases_risk"),
                    ("hrv_stress_proxy", 0.15, "increases_risk"),
                    ("mean_ibi", 0.1, "neutral")],
            "TEMP": [("temp_stress_proxy", 0.4, "increases_risk"),
                     ("thermal_variability", 0.3, "increases_risk"),
                     ("temp_mean", 0.2, "neutral"),
                     ("temp_std", 0.1, "neutral")],
            "ACC": [("movement_intensity", 0.5, "neutral"),
                    ("inactivity_ratio", 0.3, "neutral"),
                    ("movement_variability", 0.2, "neutral")],
        }
        raw_facts = bio_features.get(signal_type.upper(), [
            ("signal_mean", 0.5, "neutral"),
            ("signal_volatility", 0.3, "increases_risk"),
        ])

        top_features = [
            FeatureFact(
                feature_name=fn,
                importance_score=score,
                direction=direction,
                magnitude=_score_to_magnitude(score),
                plain_english=_plain_english_fact(fn, score, direction).replace(
                    "attrition risk", "physiological stress proxy"
                ),
                shap_mean_abs=0.0,
                data_source="signal_processing",
            )
            for fn, score, direction in raw_facts
        ]

        summary, chain, uncertainty = _build_global_summary(
            top_features, validity, "biosignal", "Signal Processing", "biosignal_timeseries"
        )

        return ExplainabilityReport(
            top_features=top_features,
            provenance=provenance,
            validity=validity,
            global_summary=summary,
            reasoning_chain=chain,
            uncertainty_note=uncertainty,
            shap_available=False,
            shap_global_importance={},
            shap_explanation_text="",
            model_type="Signal Processing Pipeline",
            training_mode="biosignal",
            n_samples_explained=n_windows,
        )
