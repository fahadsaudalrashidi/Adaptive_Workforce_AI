"""
Confidence Engine
Uncertainty quantification, statistical validity assessment,
and confidence-aware prediction scoring for the Adaptive Workforce
Intelligence Engine.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class UncertaintyEstimate:
    """Per-prediction uncertainty quantification."""
    prediction_value: float     # e.g. attrition probability
    lower_bound: float          # 95% confidence interval lower
    upper_bound: float          # 95% confidence interval upper
    interval_width: float       # upper - lower
    uncertainty_level: str      # "Low" / "Moderate" / "High" / "Very High"
    epistemic: float            # model uncertainty (0–1)
    aleatoric: float            # data noise uncertainty (0–1)
    total_uncertainty: float    # combined


@dataclass
class StatisticalValidity:
    """Overall statistical validity of a prediction or analysis."""
    level: str                  # "High" / "Medium" / "Low" / "Insufficient"
    confidence_score: float     # 0–1
    sample_size_adequate: bool
    class_balance_adequate: bool
    feature_quality: str        # "Good" / "Fair" / "Poor"
    data_quality_impact: str    # human-readable quality impact statement
    caveats: List[str] = field(default_factory=list)


@dataclass
class ConfidenceProfile:
    """Complete confidence profile for a model's predictions."""
    overall_confidence: float         # 0–1 governed score
    confidence_band: str              # "High" / "Moderate" / "Low" / "Unreliable"
    statistical_validity: StatisticalValidity
    uncertainty_estimates: List[UncertaintyEstimate]
    calibration_score: float          # how well probabilities match reality (0–1)
    prediction_stability: float       # std of probabilities across CV folds (0 = very stable)
    feature_coverage: float           # pct of expected features present (0–1)
    cross_validation_variance: float  # variance in CV AUC scores
    display_threshold_met: bool       # True if score ≥ 0.45
    summary: str


# ── Engine ───────────────────────────────────────────────────────────────────

class ConfidenceEngine:
    """
    Computes uncertainty estimates and statistical validity profiles.
    Designed to wrap any trained sklearn-compatible model.
    """

    # ── Primary interface ─────────────────────────────────────────────────

    def build_profile(
        self,
        *,
        model: Any,
        X_test: pd.DataFrame,
        y_test: Optional[pd.Series],
        auc_score: float,
        cv_scores: Optional[List[float]] = None,
        n_train: int,
        data_quality_score: float,
        feature_names: List[str],
        expected_features: Optional[List[str]] = None,
        class_weights: Optional[Dict[Any, float]] = None,
    ) -> ConfidenceProfile:
        """
        Build a full confidence profile from a trained model and test set.
        """
        # 1. Get raw probabilities
        raw_probs = self._get_probabilities(model, X_test)

        # 2. Uncertainty estimates for each sample
        estimates = self._compute_uncertainty(raw_probs, auc_score, data_quality_score)

        # 3. Statistical validity
        n_test = len(X_test)
        class_balance_ok = self._check_class_balance(y_test)
        feature_cov = self._feature_coverage(feature_names, expected_features)
        validity = self._assess_validity(
            n_train=n_train,
            n_test=n_test,
            auc_score=auc_score,
            data_quality_score=data_quality_score,
            class_balance_ok=class_balance_ok,
            feature_coverage=feature_cov,
            cv_scores=cv_scores,
        )

        # 4. Calibration & stability
        calibration = self._estimate_calibration(raw_probs, y_test, auc_score)
        stability = float(np.std(raw_probs)) if len(raw_probs) > 0 else 0.5
        cv_var = float(np.var(cv_scores)) if cv_scores else 0.0

        # 5. Overall governed confidence
        governed = self._govern(
            auc_score, n_train, data_quality_score, calibration, cv_var
        )
        band = _label(governed)
        display_ok = governed >= 0.45

        summary = self._summarise(governed, band, validity, auc_score, n_train)

        return ConfidenceProfile(
            overall_confidence=governed,
            confidence_band=band,
            statistical_validity=validity,
            uncertainty_estimates=estimates[:500],  # cap to avoid huge payloads
            calibration_score=calibration,
            prediction_stability=stability,
            feature_coverage=feature_cov,
            cross_validation_variance=cv_var,
            display_threshold_met=display_ok,
            summary=summary,
        )

    def quick_profile(
        self,
        *,
        auc_score: float,
        n_samples: int,
        data_quality_score: float,
        cv_scores: Optional[List[float]] = None,
        class_imbalance_ratio: float = 1.0,
    ) -> ConfidenceProfile:
        """
        Lightweight profile when model/test data are not available.
        Used for fast UI badges without re-running inference.
        """
        n_test = max(1, n_samples // 5)
        class_balance_ok = class_imbalance_ratio <= 5.0
        cv_var = float(np.var(cv_scores)) if cv_scores else 0.0

        validity = self._assess_validity(
            n_train=n_samples,
            n_test=n_test,
            auc_score=auc_score,
            data_quality_score=data_quality_score,
            class_balance_ok=class_balance_ok,
            feature_coverage=1.0,
            cv_scores=cv_scores,
        )

        governed = self._govern(
            auc_score, n_samples, data_quality_score, 0.70, cv_var
        )

        # Imbalance penalty
        if class_imbalance_ratio > 10:
            governed *= 0.70
        elif class_imbalance_ratio > 5:
            governed *= 0.85
        governed = round(min(1.0, max(0.0, governed)), 4)

        band = _label(governed)

        return ConfidenceProfile(
            overall_confidence=governed,
            confidence_band=band,
            statistical_validity=validity,
            uncertainty_estimates=[],
            calibration_score=0.70,
            prediction_stability=0.25,
            feature_coverage=1.0,
            cross_validation_variance=cv_var,
            display_threshold_met=governed >= 0.45,
            summary=self._summarise(governed, band, validity, auc_score, n_samples),
        )

    def assess_signal_quality(
        self,
        *,
        n_samples: int,
        n_windows: int,
        missing_pct: float,
        anomaly_pct: float,
        signal_type: str = "HR",
    ) -> StatisticalValidity:
        """
        Validity assessment for biosignal data — no model involved.
        """
        base_quality = 1.0 - missing_pct
        if anomaly_pct > 0.30:
            base_quality *= 0.60
        elif anomaly_pct > 0.20:
            base_quality *= 0.75
        elif anomaly_pct > 0.10:
            base_quality *= 0.90

        if n_windows < 10:
            base_quality *= 0.50
        elif n_windows < 30:
            base_quality *= 0.75

        caveats: List[str] = []
        if missing_pct > 0.20:
            caveats.append(f"High missing-data rate ({missing_pct:.0%}) in signal.")
        if anomaly_pct > 0.20:
            caveats.append(f"Anomalous windows: {anomaly_pct:.0%} — review raw signal.")
        if n_windows < 10:
            caveats.append(f"Only {n_windows} analysis windows — results indicative only.")
        caveats.append("Non-clinical tool. Not a diagnostic device.")

        level = (
            "High"         if base_quality >= 0.80 else
            "Medium"       if base_quality >= 0.60 else
            "Low"          if base_quality >= 0.40 else
            "Insufficient"
        )

        impact = (
            "Signal quality adequate for physiological pattern detection."
            if base_quality >= 0.70
            else "Signal quality degraded — interpret results with caution."
        )

        return StatisticalValidity(
            level=level,
            confidence_score=round(base_quality, 4),
            sample_size_adequate=n_samples >= 1000,
            class_balance_adequate=True,   # N/A for biosignal
            feature_quality="Good" if base_quality >= 0.70 else "Fair" if base_quality >= 0.50 else "Poor",
            data_quality_impact=impact,
            caveats=caveats,
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _get_probabilities(self, model: Any, X: pd.DataFrame) -> np.ndarray:
        try:
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X)
                if probs.ndim == 2:
                    return probs[:, 1].astype(float)
                return probs.astype(float)
            if hasattr(model, "decision_function"):
                raw = model.decision_function(X)
                return 1.0 / (1.0 + np.exp(-raw))
            return np.full(len(X), 0.5)
        except Exception:
            return np.full(max(len(X), 1), 0.5)

    def _compute_uncertainty(
        self, probs: np.ndarray, auc: float, quality: float
    ) -> List[UncertaintyEstimate]:
        estimates = []
        # Epistemic ~ inverse of AUC quality; Aleatoric ~ variance in probabilities
        ep_base = max(0.0, 1.0 - auc) * (1.0 - quality * 0.5)
        al_base = float(np.std(probs)) if len(probs) > 1 else 0.25
        al_base = min(al_base, 0.5)

        for p in probs:
            # 95% CI heuristic: ±1.96 × combined std
            combined_std = np.sqrt(ep_base**2 + al_base**2)
            lo = max(0.0, p - 1.96 * combined_std)
            hi = min(1.0, p + 1.96 * combined_std)
            width = hi - lo
            total = min(1.0, ep_base + al_base)
            level = (
                "Low"       if total <= 0.15 else
                "Moderate"  if total <= 0.30 else
                "High"      if total <= 0.50 else
                "Very High"
            )
            estimates.append(UncertaintyEstimate(
                prediction_value=round(float(p), 4),
                lower_bound=round(lo, 4),
                upper_bound=round(hi, 4),
                interval_width=round(width, 4),
                uncertainty_level=level,
                epistemic=round(ep_base, 4),
                aleatoric=round(al_base, 4),
                total_uncertainty=round(total, 4),
            ))
        return estimates

    def _estimate_calibration(
        self, probs: np.ndarray, y_test: Optional[pd.Series], auc: float
    ) -> float:
        if y_test is None or len(y_test) == 0 or len(probs) != len(y_test):
            # Rough proxy when ground truth absent
            return max(0.5, auc - 0.05)
        try:
            y = np.array(y_test).astype(float)
            bins = np.linspace(0, 1, 11)
            calibration_errors = []
            for lo, hi in zip(bins[:-1], bins[1:]):
                mask = (probs >= lo) & (probs < hi)
                if mask.sum() == 0:
                    continue
                mean_pred = probs[mask].mean()
                mean_actual = y[mask].mean()
                calibration_errors.append(abs(mean_pred - mean_actual))
            if not calibration_errors:
                return max(0.5, auc - 0.05)
            ece = np.mean(calibration_errors)
            return round(max(0.0, 1.0 - ece), 4)
        except Exception:
            return max(0.5, auc - 0.05)

    def _check_class_balance(self, y: Optional[pd.Series]) -> bool:
        if y is None or len(y) == 0:
            return True
        vc = y.value_counts()
        if len(vc) < 2:
            return True
        ratio = vc.max() / max(vc.min(), 1)
        return ratio <= 5.0

    def _feature_coverage(
        self, present: List[str], expected: Optional[List[str]]
    ) -> float:
        if not expected:
            return 1.0
        present_lower = {f.lower() for f in present}
        expected_lower = [f.lower() for f in expected]
        covered = sum(1 for f in expected_lower if f in present_lower)
        return round(covered / max(len(expected_lower), 1), 4)

    def _assess_validity(
        self,
        n_train: int,
        n_test: int,
        auc_score: float,
        data_quality_score: float,
        class_balance_ok: bool,
        feature_coverage: float,
        cv_scores: Optional[List[float]],
    ) -> StatisticalValidity:
        score = 1.0

        # Sample size
        size_ok = n_train >= 200
        if n_train < 50:
            score *= 0.40
        elif n_train < 100:
            score *= 0.65
        elif n_train < 200:
            score *= 0.80

        # AUC
        if auc_score < 0.60:
            score *= 0.40
        elif auc_score < 0.65:
            score *= 0.60
        elif auc_score < 0.70:
            score *= 0.75
        elif auc_score < 0.75:
            score *= 0.90

        # Quality
        if data_quality_score < 0.50:
            score *= 0.60
        elif data_quality_score < 0.65:
            score *= 0.80
        elif data_quality_score < 0.75:
            score *= 0.92

        # Class balance
        if not class_balance_ok:
            score *= 0.85

        # CV stability
        if cv_scores and len(cv_scores) >= 3:
            cv_std = float(np.std(cv_scores))
            if cv_std > 0.10:
                score *= 0.80
            elif cv_std > 0.07:
                score *= 0.90

        score = round(min(1.0, max(0.0, score)), 4)
        level = (
            "High"         if score >= 0.80 else
            "Medium"       if score >= 0.60 else
            "Low"          if score >= 0.40 else
            "Insufficient"
        )

        feat_quality = (
            "Good" if feature_coverage >= 0.80 else
            "Fair" if feature_coverage >= 0.60 else
            "Poor"
        )

        caveats: List[str] = []
        if not size_ok:
            caveats.append(f"Training size ({n_train}) below recommended minimum (200).")
        if auc_score < 0.70:
            caveats.append(f"AUC {auc_score:.3f} — model discrimination is limited.")
        if not class_balance_ok:
            caveats.append("Class imbalance detected — minority-class predictions less reliable.")
        if data_quality_score < 0.65:
            caveats.append(f"Data quality {data_quality_score:.0%} — assess for missing/noisy data.")
        if feature_coverage < 0.80:
            caveats.append(f"Feature coverage {feature_coverage:.0%} — some expected features absent.")

        impact = (
            "Data quality supports reliable analysis." if data_quality_score >= 0.75
            else f"Data quality ({data_quality_score:.0%}) may limit prediction accuracy." if data_quality_score >= 0.55
            else f"Poor data quality ({data_quality_score:.0%}) significantly limits reliability."
        )

        return StatisticalValidity(
            level=level,
            confidence_score=score,
            sample_size_adequate=size_ok,
            class_balance_adequate=class_balance_ok,
            feature_quality=feat_quality,
            data_quality_impact=impact,
            caveats=caveats,
        )

    def _govern(
        self,
        auc: float,
        n_train: int,
        quality: float,
        calibration: float,
        cv_var: float,
    ) -> float:
        score = 1.0

        if auc < 0.60:     score *= 0.40
        elif auc < 0.65:   score *= 0.60
        elif auc < 0.70:   score *= 0.75
        elif auc < 0.75:   score *= 0.88
        elif auc < 0.80:   score *= 0.95

        if n_train < 50:   score *= 0.50
        elif n_train < 100: score *= 0.70
        elif n_train < 200: score *= 0.85

        if quality < 0.40:  score *= 0.55
        elif quality < 0.60: score *= 0.75
        elif quality < 0.75: score *= 0.90

        if calibration < 0.60: score *= 0.80
        elif calibration < 0.70: score *= 0.92

        if cv_var > 0.01:    score *= 0.85
        elif cv_var > 0.005: score *= 0.93

        return round(min(1.0, max(0.0, score)), 4)

    def _summarise(
        self, governed: float, band: str, validity: StatisticalValidity,
        auc: float, n: int
    ) -> str:
        return (
            f"Overall confidence: {governed:.0%} [{band}]. "
            f"Statistical validity: {validity.level}. "
            f"Model AUC: {auc:.3f}. "
            f"Training records: {n:,}. "
            + (f"Caveats: {'; '.join(validity.caveats[:2])}" if validity.caveats else "No caveats.")
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _label(score: float) -> str:
    if score >= 0.80: return "High"
    if score >= 0.65: return "Moderate"
    if score >= 0.50: return "Low"
    return "Unreliable"


# ── Module-level convenience ──────────────────────────────────────────────────

def quick_confidence(
    auc_score: float,
    n_samples: int,
    data_quality_score: float,
    cv_scores: Optional[List[float]] = None,
    class_imbalance_ratio: float = 1.0,
) -> ConfidenceProfile:
    """Convenience wrapper for quick (no-model) confidence assessment."""
    engine = ConfidenceEngine()
    return engine.quick_profile(
        auc_score=auc_score,
        n_samples=n_samples,
        data_quality_score=data_quality_score,
        cv_scores=cv_scores,
        class_imbalance_ratio=class_imbalance_ratio,
    )
