"""
Drift Monitor — Architecture Interfaces for Enterprise Data Governance

Provides hooks and interfaces for all drift types the platform must monitor
in production. Full implementations are added as real enterprise data arrives.

Drift types monitored:
  1. SCHEMA_DRIFT      — unexpected column additions, removals, renames, type changes
  2. FEATURE_DRIFT     — feature distribution shift (mean, std, % missing, cardinality)
  3. PREDICTION_DRIFT  — output score distribution shift over time
  4. CONCEPT_DRIFT     — target label distribution shift (attrition rate changing)
  5. CALIBRATION_DRIFT — calibration quality degrading on new data
  6. MODALITY_DRIFT    — dataset type being misrouted (HR uploaded as survey, etc.)
  7. ROUTING_DRIFT     — routing confidence declining over repeated uploads

Severity levels: NONE, MINOR, MODERATE, MAJOR, CRITICAL
Each severity maps to a governance action (see DriftAction).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class DriftType(str, Enum):
    SCHEMA      = "SCHEMA_DRIFT"
    FEATURE     = "FEATURE_DRIFT"
    PREDICTION  = "PREDICTION_DRIFT"
    CONCEPT     = "CONCEPT_DRIFT"
    CALIBRATION = "CALIBRATION_DRIFT"
    MODALITY    = "MODALITY_DRIFT"
    ROUTING     = "ROUTING_DRIFT"


class DriftSeverity(str, Enum):
    NONE     = "NONE"
    MINOR    = "MINOR"
    MODERATE = "MODERATE"
    MAJOR    = "MAJOR"
    CRITICAL = "CRITICAL"


class DriftAction(str, Enum):
    NONE                 = "no_action"
    LOG_ONLY             = "log_only"
    WARN_USER            = "warn_user"
    DOWNGRADE_CONFIDENCE = "downgrade_confidence"
    BLOCK_DEPLOYMENT     = "block_deployment"
    REQUIRE_RETRAINING   = "require_retraining"


_SEVERITY_ACTION_MAP: Dict[DriftSeverity, DriftAction] = {
    DriftSeverity.NONE:     DriftAction.NONE,
    DriftSeverity.MINOR:    DriftAction.LOG_ONLY,
    DriftSeverity.MODERATE: DriftAction.WARN_USER,
    DriftSeverity.MAJOR:    DriftAction.DOWNGRADE_CONFIDENCE,
    DriftSeverity.CRITICAL: DriftAction.BLOCK_DEPLOYMENT,
}


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DriftFlag:
    drift_type:  str
    severity:    str
    metric:      str
    observed:    float
    baseline:    Optional[float]
    delta:       Optional[float]
    description: str
    action:      str
    timestamp:   float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DriftReport:
    dataset_type:    str
    has_drift:       bool
    overall_severity: str
    flags:           List[DriftFlag]
    recommended_action: str
    summary:         str
    timestamp:       float = field(default_factory=time.time)
    baseline_hash:   Optional[str] = None
    current_hash:    Optional[str] = None

    @property
    def n_critical(self) -> int:
        return sum(1 for f in self.flags if f.severity == DriftSeverity.CRITICAL)

    @property
    def n_major(self) -> int:
        return sum(1 for f in self.flags if f.severity == DriftSeverity.MAJOR)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetBaseline:
    """
    Fingerprint of a dataset used as reference for drift detection.
    Store this after a validated run and compare against future uploads.
    """
    dataset_type:      str
    column_names:      List[str]
    column_dtypes:     Dict[str, str]
    n_rows:            int
    n_cols:            int
    feature_stats:     Dict[str, Dict[str, float]]  # col → {mean, std, missing_pct}
    target_rate:       Optional[float]               # positive class rate
    routing_confidence: float
    dataset_hash:      str
    created_at:        float = field(default_factory=time.time)
    governance_version: str = "v2.4.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DatasetBaseline":
        return cls(**d)


# ─────────────────────────────────────────────────────────────────────────────
# DRIFT MONITOR
# ─────────────────────────────────────────────────────────────────────────────

class DriftMonitor:
    """
    Drift monitoring engine.

    Current state: interfaces + hooks implemented; statistical tests are
    architecture stubs ready for enterprise data integration.

    To activate full monitoring:
      1. Call `set_baseline()` after a validated analysis run
      2. Call `check_*()` methods on new uploads
      3. Wire GovernanceLogger for alerts

    None of this crashes if not called — all methods are safe-to-skip.
    """

    FEATURE_DRIFT_THRESHOLD_MODERATE = 0.20  # 20% mean shift
    FEATURE_DRIFT_THRESHOLD_MAJOR    = 0.40
    MISSING_DRIFT_THRESHOLD_MODERATE = 0.10  # 10pp increase in missing %
    MISSING_DRIFT_THRESHOLD_MAJOR    = 0.25
    PREDICTION_DRIFT_THRESHOLD_MODERATE = 0.10
    PREDICTION_DRIFT_THRESHOLD_MAJOR    = 0.20
    CONCEPT_DRIFT_THRESHOLD_MODERATE    = 0.10
    CONCEPT_DRIFT_THRESHOLD_MAJOR       = 0.20
    CALIBRATION_DRIFT_BRIER_THRESHOLD   = 0.05  # absolute increase
    ROUTING_CONF_DROP_THRESHOLD         = 0.15

    def __init__(self, baseline_path: Optional[Path] = None):
        self._baseline: Optional[DatasetBaseline] = None
        self._baseline_path = baseline_path or (
            Path(__file__).resolve().parent.parent.parent / "logs" / "drift_baseline.json"
        )
        self._load_baseline_if_exists()

    def _load_baseline_if_exists(self) -> None:
        try:
            if self._baseline_path.exists():
                with open(self._baseline_path, encoding="utf-8") as fh:
                    self._baseline = DatasetBaseline.from_dict(json.load(fh))
        except Exception:
            self._baseline = None

    def set_baseline(self, df: pd.DataFrame, dataset_type: str,
                     target_col: Optional[str] = None,
                     routing_confidence: float = 1.0) -> DatasetBaseline:
        """
        Fingerprint the current dataset as the drift baseline.
        Call after a validated, governance-approved analysis run.
        """
        feature_stats: Dict[str, Dict[str, float]] = {}
        for col in df.columns:
            try:
                nums = pd.to_numeric(df[col], errors="coerce")
                feature_stats[col] = {
                    "mean":        float(nums.mean()) if nums.notna().any() else 0.0,
                    "std":         float(nums.std())  if nums.notna().any() else 0.0,
                    "missing_pct": float(df[col].isna().mean()),
                    "n_unique":    int(df[col].nunique()),
                }
            except Exception:
                feature_stats[col] = {"mean": 0.0, "std": 0.0, "missing_pct": 0.0, "n_unique": 0}

        target_rate: Optional[float] = None
        if target_col and target_col in df.columns:
            try:
                target_rate = float((df[target_col] == "Yes").mean()
                                    if df[target_col].dtype == object
                                    else df[target_col].astype(float).mean())
            except Exception:
                target_rate = None

        baseline = DatasetBaseline(
            dataset_type       = dataset_type,
            column_names       = list(df.columns),
            column_dtypes      = {c: str(df[c].dtype) for c in df.columns},
            n_rows             = len(df),
            n_cols             = len(df.columns),
            feature_stats      = feature_stats,
            target_rate        = target_rate,
            routing_confidence = routing_confidence,
            dataset_hash       = _hash_dataframe(df),
        )

        self._baseline = baseline
        try:
            self._baseline_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._baseline_path, "w", encoding="utf-8") as fh:
                json.dump(baseline.to_dict(), fh, indent=2)
        except Exception:
            pass

        return baseline

    def check_schema_drift(self, df: pd.DataFrame) -> DriftReport:
        """
        Detect column additions, removals, renames, and type changes.
        CRITICAL if core target/ID columns are missing.
        MODERATE if non-critical columns added or removed.
        """
        flags: List[DriftFlag] = []

        if self._baseline is None:
            return _no_baseline_report(DriftType.SCHEMA, df)

        baseline_cols = set(self._baseline.column_names)
        current_cols  = set(df.columns)
        removed = baseline_cols - current_cols
        added   = current_cols  - baseline_cols

        for col in removed:
            sev = DriftSeverity.CRITICAL if col in self._baseline.column_names[:3] else DriftSeverity.MAJOR
            flags.append(DriftFlag(
                drift_type  = DriftType.SCHEMA,
                severity    = sev,
                metric      = "column_removed",
                observed    = 0.0,
                baseline    = 1.0,
                delta       = -1.0,
                description = f"Column '{col}' present in baseline but missing in new upload.",
                action      = _SEVERITY_ACTION_MAP[sev],
            ))

        for col in added:
            flags.append(DriftFlag(
                drift_type  = DriftType.SCHEMA,
                severity    = DriftSeverity.MINOR,
                metric      = "column_added",
                observed    = 1.0,
                baseline    = 0.0,
                delta       = 1.0,
                description = f"New column '{col}' not present in baseline.",
                action      = DriftAction.LOG_ONLY,
            ))

        for col in baseline_cols & current_cols:
            b_dtype = self._baseline.column_dtypes.get(col, "")
            c_dtype = str(df[col].dtype)
            if b_dtype and c_dtype != b_dtype:
                flags.append(DriftFlag(
                    drift_type  = DriftType.SCHEMA,
                    severity    = DriftSeverity.MODERATE,
                    metric      = "dtype_change",
                    observed    = 0.0,
                    baseline    = 0.0,
                    delta       = None,
                    description = f"Column '{col}': dtype changed from {b_dtype} to {c_dtype}.",
                    action      = DriftAction.WARN_USER,
                ))

        return _build_report(DriftType.SCHEMA, df, self._baseline, flags)

    def check_feature_drift(self, df: pd.DataFrame) -> DriftReport:
        """
        Detect distribution shift in numeric features.
        Uses relative mean shift as the primary metric (production: add PSI/KS test).
        """
        flags: List[DriftFlag] = []

        if self._baseline is None:
            return _no_baseline_report(DriftType.FEATURE, df)

        for col in df.columns:
            b_stats = self._baseline.feature_stats.get(col)
            if b_stats is None:
                continue

            try:
                nums = pd.to_numeric(df[col], errors="coerce")
                cur_mean    = float(nums.mean())   if nums.notna().any() else 0.0
                cur_missing = float(df[col].isna().mean())
                b_mean      = b_stats.get("mean", 0.0)
                b_missing   = b_stats.get("missing_pct", 0.0)
                b_std       = b_stats.get("std", 1.0) or 1.0

                rel_shift = abs(cur_mean - b_mean) / (abs(b_mean) + 1e-9)
                missing_delta = cur_missing - b_missing

                if rel_shift >= self.FEATURE_DRIFT_THRESHOLD_MAJOR:
                    sev = DriftSeverity.MAJOR
                elif rel_shift >= self.FEATURE_DRIFT_THRESHOLD_MODERATE:
                    sev = DriftSeverity.MODERATE
                else:
                    sev = None

                if sev:
                    flags.append(DriftFlag(
                        drift_type  = DriftType.FEATURE,
                        severity    = sev,
                        metric      = f"{col}_mean_shift",
                        observed    = cur_mean,
                        baseline    = b_mean,
                        delta       = cur_mean - b_mean,
                        description = f"Feature '{col}': mean shifted by {rel_shift:.0%} relative to baseline.",
                        action      = _SEVERITY_ACTION_MAP[sev],
                    ))

                if missing_delta >= self.MISSING_DRIFT_THRESHOLD_MAJOR:
                    flags.append(DriftFlag(
                        drift_type  = DriftType.FEATURE,
                        severity    = DriftSeverity.MAJOR,
                        metric      = f"{col}_missing_increase",
                        observed    = cur_missing,
                        baseline    = b_missing,
                        delta       = missing_delta,
                        description = f"Feature '{col}': missing rate increased by {missing_delta:.0%}.",
                        action      = DriftAction.WARN_USER,
                    ))
            except Exception:
                continue

        return _build_report(DriftType.FEATURE, df, self._baseline, flags)

    def check_prediction_drift(
        self,
        current_probs: "np.ndarray",
        baseline_mean: Optional[float] = None,
        baseline_std:  Optional[float] = None,
    ) -> DriftReport:
        """
        Detect shift in model output score distribution.
        HOOK: replace with PSI (Population Stability Index) in production.
        """
        flags: List[DriftFlag] = []

        if baseline_mean is None:
            return _stub_report(DriftType.PREDICTION, "No prediction baseline set.")

        try:
            cur_mean = float(np.mean(current_probs))
            delta    = abs(cur_mean - baseline_mean)

            if delta >= self.PREDICTION_DRIFT_THRESHOLD_MAJOR:
                sev = DriftSeverity.MAJOR
            elif delta >= self.PREDICTION_DRIFT_THRESHOLD_MODERATE:
                sev = DriftSeverity.MODERATE
            else:
                sev = DriftSeverity.NONE

            if sev != DriftSeverity.NONE:
                flags.append(DriftFlag(
                    drift_type  = DriftType.PREDICTION,
                    severity    = sev,
                    metric      = "mean_score",
                    observed    = cur_mean,
                    baseline    = baseline_mean,
                    delta       = cur_mean - baseline_mean,
                    description = f"Prediction score mean shifted: {baseline_mean:.3f} → {cur_mean:.3f}",
                    action      = _SEVERITY_ACTION_MAP[sev],
                ))
        except Exception:
            pass

        dataset_type = getattr(self._baseline, "dataset_type", "unknown") if self._baseline else "unknown"
        return _build_report(DriftType.PREDICTION, None, self._baseline, flags, dataset_type=dataset_type)

    def check_concept_drift(
        self,
        current_target_rate: float,
    ) -> DriftReport:
        """
        Detect shift in the target label rate (e.g., attrition rate changing over time).
        Triggered when a new labeled dataset arrives.
        """
        flags: List[DriftFlag] = []

        baseline_rate = getattr(self._baseline, "target_rate", None) if self._baseline else None
        if baseline_rate is None:
            return _stub_report(DriftType.CONCEPT, "No concept baseline (target rate) set.")

        delta = abs(current_target_rate - baseline_rate)
        if delta >= self.CONCEPT_DRIFT_THRESHOLD_MAJOR:
            sev = DriftSeverity.MAJOR
        elif delta >= self.CONCEPT_DRIFT_THRESHOLD_MODERATE:
            sev = DriftSeverity.MODERATE
        else:
            sev = DriftSeverity.NONE

        if sev != DriftSeverity.NONE:
            flags.append(DriftFlag(
                drift_type  = DriftType.CONCEPT,
                severity    = sev,
                metric      = "target_rate",
                observed    = current_target_rate,
                baseline    = baseline_rate,
                delta       = current_target_rate - baseline_rate,
                description = (
                    f"Target rate changed: {baseline_rate:.1%} → {current_target_rate:.1%}. "
                    "Model may need retraining."
                ),
                action      = DriftAction.REQUIRE_RETRAINING if sev == DriftSeverity.MAJOR
                              else DriftAction.WARN_USER,
            ))

        dataset_type = getattr(self._baseline, "dataset_type", "unknown") if self._baseline else "unknown"
        return _build_report(DriftType.CONCEPT, None, self._baseline, flags, dataset_type=dataset_type)

    def check_calibration_drift(
        self,
        current_brier: float,
        baseline_brier: Optional[float] = None,
    ) -> DriftReport:
        """
        Detect degradation in model calibration quality.
        Brier score increase > threshold triggers warning/downgrade.
        """
        flags: List[DriftFlag] = []
        b_brier = baseline_brier

        if b_brier is None:
            return _stub_report(DriftType.CALIBRATION, "No calibration baseline set.")

        delta = current_brier - b_brier
        if delta > self.CALIBRATION_DRIFT_BRIER_THRESHOLD:
            sev = DriftSeverity.MAJOR if delta > 0.08 else DriftSeverity.MODERATE
            flags.append(DriftFlag(
                drift_type  = DriftType.CALIBRATION,
                severity    = sev,
                metric      = "brier_score",
                observed    = current_brier,
                baseline    = b_brier,
                delta       = delta,
                description = (
                    f"Calibration degraded: Brier {b_brier:.4f} → {current_brier:.4f} "
                    f"(+{delta:.4f}). Probability estimates may be less reliable."
                ),
                action      = _SEVERITY_ACTION_MAP[sev],
            ))

        dataset_type = getattr(self._baseline, "dataset_type", "unknown") if self._baseline else "unknown"
        return _build_report(DriftType.CALIBRATION, None, self._baseline, flags, dataset_type=dataset_type)

    def check_modality_drift(
        self,
        detected_type: str,
        expected_type: str,
        routing_confidence: float,
    ) -> DriftReport:
        """
        Detect when datasets are being misrouted — HR data uploaded as survey, etc.
        """
        flags: List[DriftFlag] = []

        if detected_type != expected_type:
            flags.append(DriftFlag(
                drift_type  = DriftType.MODALITY,
                severity    = DriftSeverity.CRITICAL,
                metric      = "dataset_type",
                observed    = 0.0,
                baseline    = 1.0,
                delta       = None,
                description = (
                    f"Modality mismatch: expected '{expected_type}', "
                    f"detected '{detected_type}'. Routing may be incorrect."
                ),
                action      = DriftAction.BLOCK_DEPLOYMENT,
            ))

        if routing_confidence < 1.0 - self.ROUTING_CONF_DROP_THRESHOLD:
            flags.append(DriftFlag(
                drift_type  = DriftType.MODALITY,
                severity    = DriftSeverity.MODERATE,
                metric      = "routing_confidence",
                observed    = routing_confidence,
                baseline    = getattr(self._baseline, "routing_confidence", 1.0),
                delta       = routing_confidence - getattr(self._baseline, "routing_confidence", 1.0),
                description = f"Routing confidence dropped to {routing_confidence:.0%}.",
                action      = DriftAction.WARN_USER,
            ))

        return _build_report(DriftType.MODALITY, None, self._baseline, flags,
                             dataset_type=detected_type)

    def check_routing_drift(self, routing_confidence: float) -> DriftReport:
        """
        Detect sustained routing confidence decline across uploads.
        Placeholder for time-series routing confidence tracking.
        """
        flags: List[DriftFlag] = []
        b_conf = getattr(self._baseline, "routing_confidence", None) if self._baseline else None

        if b_conf is not None:
            delta = routing_confidence - b_conf
            if delta < -self.ROUTING_CONF_DROP_THRESHOLD:
                sev = DriftSeverity.MODERATE if delta > -0.30 else DriftSeverity.MAJOR
                flags.append(DriftFlag(
                    drift_type  = DriftType.ROUTING,
                    severity    = sev,
                    metric      = "routing_confidence",
                    observed    = routing_confidence,
                    baseline    = b_conf,
                    delta       = delta,
                    description = (
                        f"Routing confidence dropped: {b_conf:.0%} → {routing_confidence:.0%}. "
                        "Dataset characteristics may have shifted."
                    ),
                    action      = _SEVERITY_ACTION_MAP[sev],
                ))

        dataset_type = getattr(self._baseline, "dataset_type", "unknown") if self._baseline else "unknown"
        return _build_report(DriftType.ROUTING, None, self._baseline, flags, dataset_type=dataset_type)

    @property
    def has_baseline(self) -> bool:
        return self._baseline is not None

    @property
    def baseline(self) -> Optional[DatasetBaseline]:
        return self._baseline


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _hash_dataframe(df: pd.DataFrame) -> str:
    try:
        col_str = "|".join(sorted(df.columns))
        shape_str = f"{len(df)}x{len(df.columns)}"
        sample_str = str(df.iloc[:5].values.tolist()) if len(df) > 0 else ""
        return hashlib.sha256(f"{col_str}|{shape_str}|{sample_str}".encode()).hexdigest()
    except Exception:
        return "hash_error"


def _overall_severity(flags: List[DriftFlag]) -> DriftSeverity:
    if not flags:
        return DriftSeverity.NONE
    levels = [DriftSeverity.CRITICAL, DriftSeverity.MAJOR,
               DriftSeverity.MODERATE, DriftSeverity.MINOR]
    for level in levels:
        if any(f.severity == level for f in flags):
            return level
    return DriftSeverity.NONE


def _build_report(
    drift_type: DriftType,
    df: Optional[pd.DataFrame],
    baseline: Optional[DatasetBaseline],
    flags: List[DriftFlag],
    dataset_type: str = "unknown",
) -> DriftReport:
    sev = _overall_severity(flags)
    action = _SEVERITY_ACTION_MAP.get(sev, DriftAction.NONE)
    n = len(flags)
    summary = (
        f"{drift_type.value}: {n} flag(s), severity={sev.value}, action={action.value}"
        if n > 0
        else f"{drift_type.value}: no drift detected."
    )
    return DriftReport(
        dataset_type        = dataset_type,
        has_drift           = n > 0,
        overall_severity    = sev,
        flags               = flags,
        recommended_action  = action,
        summary             = summary,
        baseline_hash       = getattr(baseline, "dataset_hash", None),
        current_hash        = _hash_dataframe(df) if df is not None else None,
    )


def _no_baseline_report(drift_type: DriftType, df: Optional[pd.DataFrame]) -> DriftReport:
    return DriftReport(
        dataset_type        = "unknown",
        has_drift           = False,
        overall_severity    = DriftSeverity.NONE,
        flags               = [],
        recommended_action  = DriftAction.NONE,
        summary             = (
            f"{drift_type.value}: No baseline set. "
            "Run analysis on a validated dataset first, then call set_baseline()."
        ),
    )


def _stub_report(drift_type: DriftType, reason: str) -> DriftReport:
    return DriftReport(
        dataset_type        = "unknown",
        has_drift           = False,
        overall_severity    = DriftSeverity.NONE,
        flags               = [],
        recommended_action  = DriftAction.NONE,
        summary             = f"{drift_type.value}: {reason}",
    )


# Module-level singleton
_drift_monitor = DriftMonitor()


def get_drift_monitor() -> DriftMonitor:
    """Return the module-level singleton drift monitor."""
    return _drift_monitor
