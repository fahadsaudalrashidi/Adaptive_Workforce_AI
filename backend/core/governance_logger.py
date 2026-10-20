"""
Governance Logger — Structured Internal Logging

Captures all governance-critical events with structured records.
NEVER exposed to executive users or the Streamlit UI.

Log categories:
  - ROUTING     : dataset type decisions and confidence
  - GOVERNANCE  : confidence downgrades, hard caps applied
  - LEAKAGE     : leakage flags, severity, columns
  - CALIBRATION : Brier score, ECE, quality band
  - PAGE_FAIL   : safe_error_boundary catches
  - EXPORT      : report/CSV export attempts
  - SESSION     : session recovery and reset events
  - MODEL       : training events, drift signals
  - CONTRACT    : data contract validation outcomes
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "governance.jsonl"

logging.basicConfig(level=logging.WARNING)
_internal_logger = logging.getLogger("governance_logger")


class GovernanceEventType(str, Enum):
    ROUTING         = "ROUTING"
    GOVERNANCE      = "GOVERNANCE"
    LEAKAGE         = "LEAKAGE"
    CALIBRATION     = "CALIBRATION"
    PAGE_FAIL       = "PAGE_FAIL"
    EXPORT          = "EXPORT"
    SESSION         = "SESSION"
    MODEL           = "MODEL"
    CONTRACT        = "CONTRACT"
    DRIFT           = "DRIFT"
    REPRODUCIBILITY = "REPRODUCIBILITY"


class GovernanceSeverity(str, Enum):
    INFO     = "INFO"
    WARN     = "WARN"
    CRITICAL = "CRITICAL"


@dataclass
class GovernanceEvent:
    event_type:   str
    severity:     str
    component:    str
    dataset_type: str
    message:      str
    action:       str
    timestamp:    float = field(default_factory=time.time)
    details:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GovernanceLogger:
    """
    Singleton-friendly structured logger for all governance events.
    Writes to logs/governance.jsonl (JSONL format, append-only).
    Also emits to Python logging at WARNING+ for stderr capture.
    NEVER surfaces to executive UI.
    """

    def __init__(self, log_path: Optional[Path] = None):
        self._path = log_path or _LOG_PATH
        self._events: List[GovernanceEvent] = []
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _emit(self, event: GovernanceEvent) -> None:
        self._events.append(event)
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        except Exception:
            pass
        if event.severity in (GovernanceSeverity.WARN, GovernanceSeverity.CRITICAL):
            _internal_logger.warning(
                "[%s][%s] %s | %s | %s",
                event.severity, event.event_type, event.component,
                event.message, event.action,
            )

    def log_routing(
        self,
        dataset_type: str,
        confidence: float,
        locked: bool,
        filename: str = "",
        override: Optional[str] = None,
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.ROUTING,
            severity     = GovernanceSeverity.INFO,
            component    = "AdaptiveRouter",
            dataset_type = dataset_type,
            message      = f"Routed '{filename}' → {dataset_type} (conf={confidence:.3f}, locked={locked})",
            action       = "route_accepted" if not override else f"override_applied:{override}",
            details      = {"filename": filename, "confidence": confidence,
                            "locked": locked, "override": override},
        ))

    def log_governance_downgrade(
        self,
        component: str,
        dataset_type: str,
        original_score: float,
        new_score: float,
        reason: str,
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.GOVERNANCE,
            severity     = GovernanceSeverity.WARN,
            component    = component,
            dataset_type = dataset_type,
            message      = f"Score downgraded {original_score:.3f} → {new_score:.3f}: {reason}",
            action       = "confidence_cap_applied",
            details      = {"original": original_score, "capped": new_score, "reason": reason},
        ))

    def log_leakage(
        self,
        dataset_type: str,
        risk_level: str,
        n_critical: int,
        n_high: int,
        governed_auc: float,
    ) -> None:
        sev = GovernanceSeverity.CRITICAL if n_critical > 0 else (
            GovernanceSeverity.WARN if risk_level in ("HIGH", "MODERATE") else GovernanceSeverity.INFO
        )
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.LEAKAGE,
            severity     = sev,
            component    = "LeakageDetector",
            dataset_type = dataset_type,
            message      = (
                f"Leakage={risk_level}, critical={n_critical}, high={n_high}, "
                f"governed_auc={governed_auc:.3f}"
            ),
            action       = "auc_governed" if n_critical > 0 else "leakage_flagged",
            details      = {"risk_level": risk_level, "n_critical": n_critical,
                            "n_high": n_high, "governed_auc": governed_auc},
        ))

    def log_calibration(
        self,
        dataset_type: str,
        quality: str,
        brier_score: Optional[float],
        ece: Optional[float],
        overconfident: bool,
        underconfident: bool,
    ) -> None:
        sev = GovernanceSeverity.WARN if quality in ("Poor", "NOT_EVALUATED") else GovernanceSeverity.INFO
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.CALIBRATION,
            severity     = sev,
            component    = "CalibrationEngine",
            dataset_type = dataset_type,
            message      = (
                f"Calibration={quality}, brier={brier_score}, ece={ece}, "
                f"overconf={overconfident}, underconf={underconfident}"
            ),
            action       = "calibration_evaluated",
            details      = {"quality": quality, "brier_score": brier_score,
                            "ece": ece, "overconfident": overconfident,
                            "underconfident": underconfident},
        ))

    def log_page_fail(
        self,
        section_name: str,
        dataset_type: str,
        error_type: str,
        error_msg: str,
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.PAGE_FAIL,
            severity     = GovernanceSeverity.WARN,
            component    = f"UI:{section_name}",
            dataset_type = dataset_type,
            message      = f"Rendering failed in '{section_name}': [{error_type}] {error_msg[:200]}",
            action       = "safe_error_boundary_caught",
            details      = {"section": section_name, "error_type": error_type},
        ))

    def log_export(
        self,
        export_type: str,
        dataset_type: str,
        success: bool,
        reason: str = "",
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.EXPORT,
            severity     = GovernanceSeverity.INFO if success else GovernanceSeverity.WARN,
            component    = "ReportExport",
            dataset_type = dataset_type,
            message      = f"Export '{export_type}': {'OK' if success else 'FAILED'} — {reason}",
            action       = "export_ok" if success else "export_degraded",
            details      = {"export_type": export_type, "success": success, "reason": reason},
        ))

    def log_model_event(
        self,
        dataset_type: str,
        model_name: str,
        auc: float,
        governed_auc: float,
        n_rows: int,
        n_features: int,
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.MODEL,
            severity     = GovernanceSeverity.INFO,
            component    = "MLRouter",
            dataset_type = dataset_type,
            message      = (
                f"Model={model_name}, auc={auc:.3f}, governed={governed_auc:.3f}, "
                f"rows={n_rows}, features={n_features}"
            ),
            action       = "model_trained",
            details      = {"model": model_name, "auc": auc, "governed_auc": governed_auc,
                            "n_rows": n_rows, "n_features": n_features},
        ))

    def log_contract(
        self,
        dataset_type: str,
        allows: List[str],
        blocks: List[str],
        is_biosignal: bool,
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.CONTRACT,
            severity     = GovernanceSeverity.INFO,
            component    = "DatasetContract",
            dataset_type = dataset_type,
            message      = (
                f"Contract: allows={len(allows)}, blocks={len(blocks)}, "
                f"biosignal={is_biosignal}"
            ),
            action       = "contract_applied",
            details      = {"allows": allows[:10], "blocks": blocks[:10],
                            "is_biosignal": is_biosignal},
        ))

    def log_drift(
        self,
        drift_type: str,
        dataset_type: str,
        severity: str,
        metric: str,
        observed: float,
        baseline: Optional[float],
        action: str,
    ) -> None:
        sev_map = {
            "CRITICAL": GovernanceSeverity.CRITICAL,
            "HIGH":     GovernanceSeverity.WARN,
            "MODERATE": GovernanceSeverity.WARN,
        }
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.DRIFT,
            severity     = sev_map.get(severity, GovernanceSeverity.INFO),
            component    = "DriftMonitor",
            dataset_type = dataset_type,
            message      = (
                f"Drift[{drift_type}] metric={metric}, "
                f"observed={observed:.4f}, baseline={baseline}"
            ),
            action       = action,
            details      = {"drift_type": drift_type, "metric": metric,
                            "observed": observed, "baseline": baseline},
        ))

    def log_reproducibility(
        self,
        dataset_type: str,
        dataset_hash: str,
        random_seed: int,
        preprocessing_version: str,
        model_version: str,
        governance_version: str,
    ) -> None:
        self._emit(GovernanceEvent(
            event_type   = GovernanceEventType.REPRODUCIBILITY,
            severity     = GovernanceSeverity.INFO,
            component    = "ReproducibilityTracker",
            dataset_type = dataset_type,
            message      = (
                f"Run: hash={dataset_hash[:12]}, seed={random_seed}, "
                f"preproc_v={preprocessing_version}, model_v={model_version}"
            ),
            action       = "run_fingerprinted",
            details      = {
                "dataset_hash":           dataset_hash,
                "random_seed":            random_seed,
                "preprocessing_version":  preprocessing_version,
                "model_version":          model_version,
                "governance_version":     governance_version,
            },
        ))

    def recent_events(self, n: int = 50) -> List[GovernanceEvent]:
        return self._events[-n:]

    def critical_events(self) -> List[GovernanceEvent]:
        return [e for e in self._events if e.severity == GovernanceSeverity.CRITICAL]


# Module-level singleton — import and call directly in any backend component
_logger = GovernanceLogger()


def get_governance_logger() -> GovernanceLogger:
    """Return the module-level singleton governance logger."""
    return _logger
