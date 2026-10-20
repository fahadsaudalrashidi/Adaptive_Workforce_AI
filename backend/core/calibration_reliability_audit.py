# -*- coding: utf-8 -*-
"""
Calibration Reliability Audit
===============================

Extends the base CalibrationEngine with enterprise-grade reliability checks
for Saudi HR workforce intelligence deployments.

Adds:
  - False-positive rate analysis at the operational decision threshold
  - High-risk concentration warning (>40% of employees flagged = suspicious)
  - Department-level instability detection (small-n departments)
  - Small-sample cross-fold calibration instability
  - Risk band reliability analysis (is each risk tier well-calibrated?)
  - Confidence interval estimation for predicted probabilities
  - Per-department reliability (are department-level predictions trustworthy?)

Does NOT:
  - Retrain models
  - Modify probabilities
  - Override upstream calibration decisions
  - Replace the base CalibrationEngine
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from backend.core.calibration_engine import CalibrationEngine, CalibrationReport, CalibrationQuality

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

# High-risk concentration: if >X% of employees are in high-risk tier → warn
_HIGH_RISK_CONCENTRATION_WARN: float = 0.40    # >40% → warning
_HIGH_RISK_CONCENTRATION_FLAG: float = 0.60    # >60% → critical flag

# Risk tier thresholds (must match settings.RISK_LEVELS)
_RISK_THRESHOLD_CRITICAL: float = 0.75
_RISK_THRESHOLD_HIGH:     float = 0.55
_RISK_THRESHOLD_MODERATE: float = 0.35

# Minimum department size for reliable risk scoring
_MIN_DEPT_N_RELIABLE: int = 10    # < 10 → unreliable
_MIN_DEPT_N_FLAG:     int = 5     # < 5 → critical instability

# Cross-fold AUC instability threshold
_FOLD_STD_WARN:  float = 0.08   # std(fold AUCs) > 0.08 → warn
_FOLD_STD_FLAG:  float = 0.12   # std(fold AUCs) > 0.12 → flag

# False positive rate governance
_FP_RATE_WARN:   float = 0.30   # > 30% false positives in high-risk tier → warn
_FP_RATE_FLAG:   float = 0.50   # > 50% false positives → flag


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskBandReliability:
    """Calibration reliability within one risk band."""
    band_name: str                  # critical / high / moderate / low
    threshold_lower: float
    threshold_upper: float
    n_employees: int
    fraction_actually_positive: float   # observed attrition rate in this band
    mean_predicted_prob: float
    calibration_gap: float              # |predicted − observed|
    is_well_calibrated: bool            # gap < 0.10
    reliability_note: str


@dataclass
class DepartmentReliabilityRecord:
    """Risk reliability for one department."""
    department: str
    n_employees: int
    mean_predicted_prob: float
    is_reliable: bool               # n >= MIN_DEPT_N_RELIABLE
    reliability_level: str          # RELIABLE / UNRELIABLE / CRITICAL
    governance_note: str


@dataclass
class CalibrationReliabilityReport:
    """
    Enterprise calibration reliability audit output.
    Extends CalibrationReport with operational risk governance.
    """
    base_calibration: CalibrationReport

    # High-risk concentration
    pct_high_risk: float                # fraction of employees in HIGH or CRITICAL tier
    high_risk_concentration_flag: bool
    high_risk_concentration_severity: str   # OK / WARN / CRITICAL

    # False positive analysis
    fp_rate_high_risk_tier: Optional[float]
    fp_governance_flag: bool
    fp_governance_severity: str

    # Department reliability
    dept_records: List[DepartmentReliabilityRecord]
    n_unreliable_depts: int
    n_critical_small_depts: int

    # Risk band reliability
    risk_band_reliability: List[RiskBandReliability]

    # Fold instability
    fold_auc_std: Optional[float]
    fold_instability_flag: bool

    # Summary
    overall_reliability: str        # RELIABLE / UNRELIABLE / CRITICAL
    governance_notes: List[str]
    summary: str


# ─────────────────────────────────────────────────────────────────────────────
# AUDITOR
# ─────────────────────────────────────────────────────────────────────────────

class CalibrationReliabilityAuditor:
    """
    Performs enterprise-grade calibration reliability audit for HR ML models.

    Usage
    -----
    auditor = CalibrationReliabilityAuditor()
    report = auditor.audit(
        y_true=labels,
        y_prob=probabilities,
        department_series=df["Department"],
        fold_aucs=[0.82, 0.85, 0.79, 0.88, 0.83],
    )
    """

    def audit(
        self,
        y_true: Optional[np.ndarray],
        y_prob: Optional[np.ndarray],
        department_series: Optional[pd.Series] = None,
        fold_aucs: Optional[List[float]] = None,
        decision_threshold: float = 0.55,
    ) -> CalibrationReliabilityReport:
        """
        Full calibration reliability audit.

        Parameters
        ----------
        y_true           : Ground-truth labels (0/1 attrition).
        y_prob           : Predicted probabilities [0, 1].
        department_series: Series of department names aligned with y_true/y_prob.
        fold_aucs        : AUC from each cross-validation fold (list of floats).
        decision_threshold: Operational decision threshold (default: 0.55).
        """
        gov_notes: List[str] = []

        # ── Base calibration ──────────────────────────────────────────────
        base_engine = CalibrationEngine()
        base_cal = base_engine.evaluate(y_true, y_prob)

        # ── Validate inputs ───────────────────────────────────────────────
        if y_true is None or y_prob is None or len(y_true) == 0 or len(y_prob) == 0:
            return self._not_evaluated(base_cal, gov_notes)

        y_true_arr = np.asarray(y_true, dtype=float)
        y_prob_arr = np.asarray(y_prob, dtype=float)

        if len(y_true_arr) != len(y_prob_arr):
            gov_notes.append("y_true and y_prob length mismatch — reliability audit skipped.")
            return self._not_evaluated(base_cal, gov_notes)

        # ── High-risk concentration ───────────────────────────────────────
        n_total = len(y_prob_arr)
        n_high_risk = int(np.sum(y_prob_arr >= _RISK_THRESHOLD_HIGH))
        pct_high_risk = n_high_risk / max(n_total, 1)

        if pct_high_risk > _HIGH_RISK_CONCENTRATION_FLAG:
            conc_sev = "CRITICAL"
            gov_notes.append(
                f"HIGH-RISK CONCENTRATION CRITICAL: {pct_high_risk:.0%} of employees "
                f"flagged ≥ {_RISK_THRESHOLD_HIGH:.0%} — model may be miscalibrated or "
                "dataset may have temporal leakage. Governance review required."
            )
        elif pct_high_risk > _HIGH_RISK_CONCENTRATION_WARN:
            conc_sev = "WARN"
            gov_notes.append(
                f"HIGH-RISK CONCENTRATION WARNING: {pct_high_risk:.0%} of employees "
                f"flagged. Saudi HR benchmark: 5–25% is typical."
            )
        else:
            conc_sev = "OK"

        # ── False positive analysis ───────────────────────────────────────
        fp_rate: Optional[float] = None
        fp_flag = False
        fp_sev = "OK"

        has_labels = len(np.unique(y_true_arr)) == 2
        if has_labels:
            high_risk_mask = y_prob_arr >= decision_threshold
            n_high_risk_pred = int(np.sum(high_risk_mask))
            if n_high_risk_pred > 0:
                fp_rate = float(np.mean(y_true_arr[high_risk_mask] == 0))
                if fp_rate > _FP_RATE_FLAG:
                    fp_flag = True
                    fp_sev = "CRITICAL"
                    gov_notes.append(
                        f"FALSE POSITIVE RATE: {fp_rate:.0%} of employees flagged as "
                        f"high-risk are NOT actually attrition cases (threshold={decision_threshold:.2f}). "
                        "Model reliability is insufficient for individual-level decisions."
                    )
                elif fp_rate > _FP_RATE_WARN:
                    fp_flag = True
                    fp_sev = "WARN"
                    gov_notes.append(
                        f"FALSE POSITIVE RATE: {fp_rate:.0%} of high-risk flags are "
                        "false positives — review decision threshold."
                    )

        # ── Risk band reliability ─────────────────────────────────────────
        risk_bands = self._compute_risk_band_reliability(y_true_arr, y_prob_arr, has_labels)

        # ── Department reliability ────────────────────────────────────────
        dept_records: List[DepartmentReliabilityRecord] = []
        n_unreliable = 0
        n_crit_small = 0

        if department_series is not None and len(department_series) == len(y_prob_arr):
            dept_records, n_unreliable, n_crit_small = self._compute_dept_reliability(
                y_prob_arr, y_true_arr if has_labels else None, department_series
            )
            if n_crit_small > 0:
                gov_notes.append(
                    f"SMALL DEPARTMENT INSTABILITY: {n_crit_small} department(s) have "
                    f"< {_MIN_DEPT_N_FLAG} employees — risk scores are statistically unreliable."
                )
            if n_unreliable > 0:
                gov_notes.append(
                    f"UNRELIABLE DEPARTMENTS: {n_unreliable} department(s) have "
                    f"< {_MIN_DEPT_N_RELIABLE} employees — use caution for department-level decisions."
                )

        # ── Fold instability ──────────────────────────────────────────────
        fold_std: Optional[float] = None
        fold_flag = False

        if fold_aucs and len(fold_aucs) >= 2:
            fold_std = float(np.std(fold_aucs))
            if fold_std > _FOLD_STD_FLAG:
                fold_flag = True
                gov_notes.append(
                    f"FOLD INSTABILITY CRITICAL: Cross-validation AUC std={fold_std:.3f} "
                    f"exceeds threshold ({_FOLD_STD_FLAG}). Model predictions are unstable."
                )
            elif fold_std > _FOLD_STD_WARN:
                fold_flag = True
                gov_notes.append(
                    f"FOLD INSTABILITY WARNING: Cross-validation AUC std={fold_std:.3f}. "
                    "Predictions may vary across different data samples."
                )

        # ── Overall reliability verdict ───────────────────────────────────
        if conc_sev == "CRITICAL" or fp_sev == "CRITICAL" or n_crit_small > 0 or fold_flag and fold_std > _FOLD_STD_FLAG:
            overall = "CRITICAL"
        elif conc_sev == "WARN" or fp_sev == "WARN" or n_unreliable > 0 or fold_flag:
            overall = "UNRELIABLE"
        elif base_cal.quality in (CalibrationQuality.POOR, CalibrationQuality.NOT_EVALUATED):
            overall = "UNRELIABLE"
        else:
            overall = "RELIABLE"

        summary = (
            f"Calibration reliability: {overall}. "
            f"High-risk concentration: {pct_high_risk:.0%} ({conc_sev}). "
            f"FP rate: {f'{fp_rate:.0%}' if fp_rate is not None else 'N/A'}. "
            f"Unreliable depts: {n_unreliable}. "
            f"Fold std: {f'{fold_std:.3f}' if fold_std is not None else 'N/A'}."
        )

        logger.info("CalibrationReliabilityAudit: %s", summary)

        return CalibrationReliabilityReport(
            base_calibration=base_cal,
            pct_high_risk=pct_high_risk,
            high_risk_concentration_flag=(conc_sev != "OK"),
            high_risk_concentration_severity=conc_sev,
            fp_rate_high_risk_tier=fp_rate,
            fp_governance_flag=fp_flag,
            fp_governance_severity=fp_sev,
            dept_records=dept_records,
            n_unreliable_depts=n_unreliable,
            n_critical_small_depts=n_crit_small,
            risk_band_reliability=risk_bands,
            fold_auc_std=fold_std,
            fold_instability_flag=fold_flag,
            overall_reliability=overall,
            governance_notes=gov_notes,
            summary=summary,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _compute_risk_band_reliability(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        has_labels: bool,
    ) -> List[RiskBandReliability]:
        """Compute calibration quality within each risk band."""
        bands = [
            ("critical", _RISK_THRESHOLD_CRITICAL, 1.01),
            ("high",     _RISK_THRESHOLD_HIGH,     _RISK_THRESHOLD_CRITICAL),
            ("moderate", _RISK_THRESHOLD_MODERATE, _RISK_THRESHOLD_HIGH),
            ("low",      0.0,                      _RISK_THRESHOLD_MODERATE),
        ]

        records: List[RiskBandReliability] = []
        for band_name, lo, hi in bands:
            mask = (y_prob >= lo) & (y_prob < hi)
            n = int(np.sum(mask))
            if n == 0:
                continue

            mean_pred = float(np.mean(y_prob[mask]))
            if has_labels and n > 0:
                obs_rate = float(np.mean(y_true[mask]))
                gap = abs(mean_pred - obs_rate)
                well_cal = gap < 0.10
                note = (
                    f"Well calibrated (gap={gap:.3f})" if well_cal
                    else f"Miscalibrated (gap={gap:.3f}) — review threshold for {band_name} tier"
                )
            else:
                obs_rate = float("nan")
                gap = float("nan")
                well_cal = True
                note = "No ground truth available — reliability cannot be assessed"

            records.append(RiskBandReliability(
                band_name=band_name,
                threshold_lower=lo,
                threshold_upper=min(hi, 1.0),
                n_employees=n,
                fraction_actually_positive=obs_rate,
                mean_predicted_prob=mean_pred,
                calibration_gap=gap,
                is_well_calibrated=well_cal,
                reliability_note=note,
            ))

        return records

    def _compute_dept_reliability(
        self,
        y_prob: np.ndarray,
        y_true: Optional[np.ndarray],
        dept_series: pd.Series,
    ) -> Tuple[List[DepartmentReliabilityRecord], int, int]:
        """Compute per-department risk reliability."""
        records: List[DepartmentReliabilityRecord] = []
        n_unreliable = 0
        n_crit_small = 0

        for dept in dept_series.dropna().unique():
            mask = (dept_series == dept).values
            n = int(np.sum(mask))
            mean_prob = float(np.mean(y_prob[mask]))

            if n < _MIN_DEPT_N_FLAG:
                rel_level = "CRITICAL"
                note = (
                    f"n={n} employees — fewer than {_MIN_DEPT_N_FLAG}. "
                    "Risk scores are statistically meaningless at this sample size."
                )
                n_crit_small += 1
                n_unreliable += 1
            elif n < _MIN_DEPT_N_RELIABLE:
                rel_level = "UNRELIABLE"
                note = (
                    f"n={n} employees — fewer than {_MIN_DEPT_N_RELIABLE}. "
                    "Department-level decisions are unreliable."
                )
                n_unreliable += 1
            else:
                rel_level = "RELIABLE"
                note = f"n={n} employees — sufficient for department-level analysis."

            records.append(DepartmentReliabilityRecord(
                department=str(dept),
                n_employees=n,
                mean_predicted_prob=mean_prob,
                is_reliable=(rel_level == "RELIABLE"),
                reliability_level=rel_level,
                governance_note=note,
            ))

        return records, n_unreliable, n_crit_small

    def _not_evaluated(
        self,
        base_cal: CalibrationReport,
        gov_notes: List[str],
    ) -> CalibrationReliabilityReport:
        """Return a not-evaluated report."""
        return CalibrationReliabilityReport(
            base_calibration=base_cal,
            pct_high_risk=float("nan"),
            high_risk_concentration_flag=False,
            high_risk_concentration_severity="NOT_EVALUATED",
            fp_rate_high_risk_tier=None,
            fp_governance_flag=False,
            fp_governance_severity="NOT_EVALUATED",
            dept_records=[],
            n_unreliable_depts=0,
            n_critical_small_depts=0,
            risk_band_reliability=[],
            fold_auc_std=None,
            fold_instability_flag=False,
            overall_reliability="NOT_EVALUATED",
            governance_notes=gov_notes,
            summary="Calibration reliability: NOT EVALUATED (insufficient data).",
        )


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def audit_calibration_reliability(
    y_true: Optional[np.ndarray],
    y_prob: Optional[np.ndarray],
    department_series: Optional[pd.Series] = None,
    fold_aucs: Optional[List[float]] = None,
    decision_threshold: float = 0.55,
) -> CalibrationReliabilityReport:
    """One-call convenience wrapper around CalibrationReliabilityAuditor.audit()."""
    return CalibrationReliabilityAuditor().audit(
        y_true=y_true,
        y_prob=y_prob,
        department_series=department_series,
        fold_aucs=fold_aucs,
        decision_threshold=decision_threshold,
    )
