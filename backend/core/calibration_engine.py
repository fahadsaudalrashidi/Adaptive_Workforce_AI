"""
Calibration Engine
==================
Computes probability calibration quality for binary classifiers.

Outputs CalibrationReport with:
  - Brier score (0=perfect, 0.25=random coin flip)
  - Expected Calibration Error (ECE)
  - Reliability diagram data (bin-level observed vs. predicted)
  - Overconfidence / underconfidence detection
  - CalibrationQuality enum: Good / Moderate / Poor / Not Evaluated

Design rules:
  - Never raises to caller — returns Not Evaluated on any exception
  - All thresholds are constants at module top for easy tuning
  - Language is statistical (associated, probabilistic) — never causal
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

# Brier score thresholds (0 = perfect, 0.25 = coin flip)
_BRIER_GOOD     = 0.10   # ≤ Good
_BRIER_MODERATE = 0.18   # ≤ Moderate  (> Poor threshold = Poor)

# Expected Calibration Error thresholds
_ECE_GOOD     = 0.05
_ECE_MODERATE = 0.10

# Overconfidence: mean predicted prob much higher than mean observed rate
_OVERCONF_THRESHOLD = 0.10   # >10pp gap = overconfident
_UNDERCONF_THRESHOLD = 0.10  # >10pp gap = underconfident

# Reliability diagram bins
_N_BINS = 10


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS / DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

class CalibrationQuality(str, Enum):
    GOOD         = "Good"
    MODERATE     = "Moderate"
    POOR         = "Poor"
    NOT_EVALUATED = "Not Evaluated"


@dataclass
class ReliabilityBin:
    """One bin of the reliability diagram."""
    bin_lower: float
    bin_upper: float
    mean_predicted: float
    fraction_positive: float
    n_samples: int


@dataclass
class CalibrationReport:
    """
    Calibration quality assessment for a binary probability classifier.
    All language uses statistical framing — no causal claims.
    """
    quality:              CalibrationQuality
    brier_score:          Optional[float]    # None if not evaluated
    ece:                  Optional[float]    # Expected Calibration Error; None if not evaluated
    overconfident:        bool               # predicted probs >> observed rates
    underconfident:       bool               # predicted probs << observed rates
    mean_predicted_prob:  Optional[float]
    mean_observed_rate:   Optional[float]
    reliability_bins:     List[ReliabilityBin] = field(default_factory=list)
    summary:              str = ""
    caveats:              List[str] = field(default_factory=list)
    n_samples:            int = 0


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    return float(np.mean((y_prob - y_true) ** 2))


def _expected_calibration_error(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = _N_BINS,
) -> Tuple[float, List[ReliabilityBin]]:
    """
    Compute ECE and reliability diagram bins.
    Returns (ece, list[ReliabilityBin]).
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins[1:-1])  # 0 … n_bins-1

    ece_weighted = 0.0
    reliability_bins: List[ReliabilityBin] = []
    n = len(y_true)

    for b in range(n_bins):
        mask = bin_indices == b
        n_b = int(np.sum(mask))
        if n_b == 0:
            continue
        mean_pred = float(np.mean(y_prob[mask]))
        frac_pos  = float(np.mean(y_true[mask]))
        ece_weighted += (n_b / n) * abs(mean_pred - frac_pos)
        reliability_bins.append(ReliabilityBin(
            bin_lower        = float(bins[b]),
            bin_upper        = float(bins[b + 1]),
            mean_predicted   = round(mean_pred, 4),
            fraction_positive= round(frac_pos, 4),
            n_samples        = n_b,
        ))

    return round(float(ece_weighted), 6), reliability_bins


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

class CalibrationEngine:
    """
    Assess probability calibration quality for binary classifiers.

    Usage:
        engine = CalibrationEngine()
        report = engine.evaluate(y_true, y_prob)
    """

    def evaluate(
        self,
        y_true: Optional[np.ndarray],
        y_prob: Optional[np.ndarray],
    ) -> CalibrationReport:
        """
        Evaluate calibration quality.

        Parameters
        ----------
        y_true : array-like of 0/1 ground-truth labels
        y_prob : array-like of predicted probabilities in [0, 1]

        Returns
        -------
        CalibrationReport — never raises; returns Not Evaluated on any error.
        """
        not_evaluated = CalibrationReport(
            quality              = CalibrationQuality.NOT_EVALUATED,
            brier_score          = None,
            ece                  = None,
            overconfident        = False,
            underconfident       = False,
            mean_predicted_prob  = None,
            mean_observed_rate   = None,
            summary              = "Calibration not evaluated — ground-truth labels or predicted probabilities not available.",
            caveats              = ["Calibration quality could not be assessed. Probability outputs may be over- or under-confident."],
            n_samples            = 0,
        )

        if y_true is None or y_prob is None:
            return not_evaluated

        try:
            yt = np.asarray(y_true, dtype=float).ravel()
            yp = np.asarray(y_prob, dtype=float).ravel()

            if len(yt) != len(yp) or len(yt) < 20:
                not_evaluated.summary = (
                    "Calibration not evaluated — insufficient samples "
                    f"(need ≥20, got {len(yt)})."
                )
                return not_evaluated

            if len(np.unique(yt)) < 2:
                not_evaluated.summary = "Calibration not evaluated — only one class present in y_true."
                return not_evaluated

            # Clip probabilities to avoid log(0)
            yp = np.clip(yp, 1e-7, 1 - 1e-7)

            brier     = _brier_score(yt, yp)
            ece, bins = _expected_calibration_error(yt, yp)

            mean_pred = float(np.mean(yp))
            mean_obs  = float(np.mean(yt))
            gap = mean_pred - mean_obs
            overconfident  = gap  >  _OVERCONF_THRESHOLD
            underconfident = gap  < -_UNDERCONF_THRESHOLD

            # Classify quality
            if brier <= _BRIER_GOOD and ece <= _ECE_GOOD:
                quality = CalibrationQuality.GOOD
            elif brier <= _BRIER_MODERATE and ece <= _ECE_MODERATE:
                quality = CalibrationQuality.MODERATE
            else:
                quality = CalibrationQuality.POOR

            caveats: List[str] = []
            if overconfident:
                caveats.append(
                    f"Model is overconfident: mean predicted probability ({mean_pred:.1%}) "
                    f"exceeds mean observed rate ({mean_obs:.1%}) by {gap:.1%}. "
                    "Probabilities may be inflated — apply probability calibration before use."
                )
            if underconfident:
                caveats.append(
                    f"Model is underconfident: mean predicted probability ({mean_pred:.1%}) "
                    f"is below mean observed rate ({mean_obs:.1%}) by {abs(gap):.1%}. "
                    "Risk scores may be understated."
                )
            if quality == CalibrationQuality.POOR:
                caveats.append(
                    f"Poor calibration (Brier={brier:.3f}, ECE={ece:.3f}) — "
                    "probability outputs should not be used as literal risk percentages without recalibration."
                )

            summary = (
                f"Calibration quality: {quality.value}. "
                f"Brier score: {brier:.4f} (0=perfect, 0.25=random). "
                f"ECE: {ece:.4f}. "
                f"Mean predicted: {mean_pred:.1%} vs. observed: {mean_obs:.1%}."
                + (" Overconfident." if overconfident else "")
                + (" Underconfident." if underconfident else "")
            )

            return CalibrationReport(
                quality              = quality,
                brier_score          = round(brier, 6),
                ece                  = round(ece, 6),
                overconfident        = overconfident,
                underconfident       = underconfident,
                mean_predicted_prob  = round(mean_pred, 4),
                mean_observed_rate   = round(mean_obs, 4),
                reliability_bins     = bins,
                summary              = summary,
                caveats              = caveats,
                n_samples            = len(yt),
            )

        except Exception as exc:
            logger.warning("CalibrationEngine.evaluate failed: %s", exc)
            not_evaluated.summary = f"Calibration evaluation failed: {exc}"
            return not_evaluated


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL CONVENIENCE
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_calibration(
    y_true: Optional[np.ndarray],
    y_prob: Optional[np.ndarray],
) -> CalibrationReport:
    """Convenience wrapper around CalibrationEngine().evaluate()."""
    return CalibrationEngine().evaluate(y_true, y_prob)
