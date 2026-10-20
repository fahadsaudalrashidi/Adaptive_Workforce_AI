"""
Telemetry Engine
Enterprise-grade audit logging for every routing and analysis decision.

Every significant decision produces a TelemetryEvent:
  - Dataset uploads
  - Modality classification results
  - Routing confidence scores
  - Guard violations and blocks
  - Analysis executions
  - Errors and degradations

TelemetrySession: session-scoped audit trail.
All data stored in-memory; optional SQLite flush.

Events carry:
  timestamp, event_type, module, payload, confidence, duration_ms
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import sqlite3
import threading
import time
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


# ── Event types ───────────────────────────────────────────────────────────────

class EventType:
    UPLOAD             = "UPLOAD"
    MODALITY_CLASSIFIED= "MODALITY_CLASSIFIED"
    CONFIDENCE_SCORED  = "CONFIDENCE_SCORED"
    SEMANTIC_MAPPED    = "SEMANTIC_MAPPED"
    GUARD_PASSED       = "GUARD_PASSED"
    GUARD_BLOCKED      = "GUARD_BLOCKED"
    GUARD_WARNED       = "GUARD_WARNED"
    SANDBOX_VALIDATED  = "SANDBOX_VALIDATED"
    ANALYSIS_STARTED   = "ANALYSIS_STARTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED    = "ANALYSIS_FAILED"
    PIPELINE_DEGRADED  = "PIPELINE_DEGRADED"
    ML_TRAINED         = "ML_TRAINED"
    BIOSIGNAL_ANALYSED = "BIOSIGNAL_ANALYSED"
    REPORT_GENERATED   = "REPORT_GENERATED"
    PAGE_RENDERED      = "PAGE_RENDERED"
    PAGE_BLOCKED       = "PAGE_BLOCKED"
    ERROR              = "ERROR"
    SESSION_START      = "SESSION_START"
    SESSION_END        = "SESSION_END"
    ASSUMPTION_LOGGED  = "ASSUMPTION_LOGGED"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class TelemetryEvent:
    event_id:       str
    session_id:     str
    timestamp:      str                  # ISO 8601
    event_type:     str
    module:         str                  # which module produced this
    description:    str
    payload:        Dict[str, Any]       # structured data for the event
    confidence:     Optional[float]      # routing/analysis confidence if applicable
    duration_ms:    Optional[float]      # execution duration if measured
    severity:       str                  # "info" / "warning" / "error" / "critical"
    dataset_hash:   Optional[str]        # anonymised hash of dataset


@dataclass
class SessionSummary:
    session_id:         str
    started_at:         str
    ended_at:           Optional[str]
    n_events:           int
    n_uploads:          int
    n_analyses:         int
    n_guard_blocks:     int
    n_guard_warnings:   int
    n_errors:           int
    modalities_seen:    List[str]
    analyses_run:       List[str]
    analyses_blocked:   List[str]
    overall_health:     float            # 0–1 session health score
    provenance:         List[str]


# ── Engine ───────────────────────────────────────────────────────────────────

_DB_PATH = Path(__file__).parent.parent.parent / "telemetry.db"


class TelemetryEngine:
    """
    Session-scoped telemetry engine.
    Thread-safe. All writes go through the _lock.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        persist_to_db: bool = False,
        db_path: Optional[Path] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:16]
        self._events: List[TelemetryEvent] = []
        self._lock = threading.Lock()
        self._started_at = _now()
        self._persist = persist_to_db
        self._db_path = db_path or _DB_PATH

        if self._persist:
            self._init_db()

        self.log_event(
            event_type=EventType.SESSION_START,
            module="telemetry_engine",
            description=f"Telemetry session started: {self.session_id}",
            payload={"session_id": self.session_id},
            severity="info",
        )

    # ── Core logging ──────────────────────────────────────────────────────────

    def log_event(
        self,
        event_type: str,
        module: str,
        description: str,
        payload: Optional[Dict[str, Any]] = None,
        confidence: Optional[float] = None,
        duration_ms: Optional[float] = None,
        severity: str = "info",
        dataset_hash: Optional[str] = None,
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            event_id=str(uuid.uuid4())[:12],
            session_id=self.session_id,
            timestamp=_now(),
            event_type=event_type,
            module=module,
            description=description,
            payload=payload or {},
            confidence=round(confidence, 4) if confidence is not None else None,
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            severity=severity,
            dataset_hash=dataset_hash,
        )
        with self._lock:
            self._events.append(event)
        if self._persist:
            self._write_db(event)
        if severity in ("error", "critical"):
            logger.warning(f"[Telemetry][{event_type}] {description}")
        return event

    # ── Specialised log helpers ───────────────────────────────────────────────

    def log_upload(self, filename: str, n_rows: int, n_cols: int, df_hash: Optional[str] = None) -> TelemetryEvent:
        return self.log_event(
            EventType.UPLOAD,
            module="upload_handler",
            description=f"Dataset uploaded: '{filename}' ({n_rows:,}×{n_cols})",
            payload={"filename": filename, "n_rows": n_rows, "n_cols": n_cols},
            dataset_hash=df_hash,
        )

    def log_modality(self, modality: str, confidence: float, sub_modality: str, validity: float) -> TelemetryEvent:
        return self.log_event(
            EventType.MODALITY_CLASSIFIED,
            module="modality_classifier",
            description=f"Modality classified as '{modality}' ({confidence:.0%} confidence)",
            payload={"modality": modality, "sub_modality": sub_modality, "validity_score": validity},
            confidence=confidence,
            severity="warning" if confidence < 0.50 else "info",
        )

    def log_confidence(self, dataset_type: str, confidence: float, band: str, suppressed: List[str]) -> TelemetryEvent:
        return self.log_event(
            EventType.CONFIDENCE_SCORED,
            module="dataset_confidence_engine",
            description=f"Routing confidence: {band} ({confidence:.0%}) for '{dataset_type}'",
            payload={"dataset_type": dataset_type, "confidence": confidence, "band": band, "suppressed": suppressed},
            confidence=confidence,
            severity="warning" if confidence < 0.50 else "info",
        )

    def log_semantic_map(self, n_cols: int, dominant_role: str, coherence: float, target_candidates: List[str]) -> TelemetryEvent:
        return self.log_event(
            EventType.SEMANTIC_MAPPED,
            module="semantic_column_mapper",
            description=f"Semantic mapping: {n_cols} columns, dominant={dominant_role}, coherence={coherence:.0%}",
            payload={"n_cols": n_cols, "dominant_role": dominant_role, "coherence": coherence, "targets": target_candidates},
        )

    def log_guard_result(self, analysis: str, allowed: bool, violations: List[str], warnings: List[str]) -> TelemetryEvent:
        etype = EventType.GUARD_PASSED if allowed else EventType.GUARD_BLOCKED
        severity = "info" if allowed else "warning"
        description = (
            f"Guard: '{analysis}' {'ALLOWED' if allowed else 'BLOCKED'}"
            + (f" — {violations[0][:80]}" if violations else "")
        )
        return self.log_event(
            etype,
            module="fail_safe_guardrails",
            description=description,
            payload={"analysis": analysis, "violations": violations, "warnings": warnings},
            severity=severity,
        )

    def log_sandbox(self, n_available: int, n_blocked: int, health: float, critical_failures: List[str]) -> TelemetryEvent:
        severity = "critical" if critical_failures else ("warning" if n_blocked > n_available else "info")
        return self.log_event(
            EventType.SANDBOX_VALIDATED,
            module="fail_safe_guardrails",
            description=f"Sandbox: {n_available} allowed, {n_blocked} blocked, health={health:.0%}",
            payload={
                "n_available": n_available, "n_blocked": n_blocked,
                "health": health, "critical_failures": critical_failures,
            },
            severity=severity,
        )

    def log_analysis(
        self, analysis: str, duration_ms: float,
        success: bool, model_type: Optional[str] = None, auc: Optional[float] = None,
    ) -> TelemetryEvent:
        etype = EventType.ANALYSIS_COMPLETED if success else EventType.ANALYSIS_FAILED
        return self.log_event(
            etype,
            module="analysis_pipeline",
            description=f"Analysis '{analysis}': {'completed' if success else 'FAILED'} ({duration_ms:.0f}ms)",
            payload={"analysis": analysis, "model_type": model_type, "auc": auc},
            duration_ms=duration_ms,
            severity="error" if not success else "info",
        )

    def log_assumption(self, module: str, assumption: str, confidence: float) -> TelemetryEvent:
        return self.log_event(
            EventType.ASSUMPTION_LOGGED,
            module=module,
            description=f"Assumption: {assumption}",
            payload={"assumption": assumption},
            confidence=confidence,
            severity="warning" if confidence < 0.60 else "info",
        )

    def log_degradation(self, module: str, reason: str, fallback: str) -> TelemetryEvent:
        return self.log_event(
            EventType.PIPELINE_DEGRADED,
            module=module,
            description=f"Pipeline degraded: {reason} → fallback: {fallback}",
            payload={"reason": reason, "fallback": fallback},
            severity="warning",
        )

    def log_error(self, module: str, error: str, context: Optional[Dict] = None) -> TelemetryEvent:
        return self.log_event(
            EventType.ERROR,
            module=module,
            description=f"Error in {module}: {error[:200]}",
            payload={"error": error, "context": context or {}},
            severity="error",
        )

    def log_page_render(self, page: str, allowed: bool, reason: str = "") -> TelemetryEvent:
        etype = EventType.PAGE_RENDERED if allowed else EventType.PAGE_BLOCKED
        return self.log_event(
            etype,
            module="frontend",
            description=f"Page '{page}': {'rendered' if allowed else 'BLOCKED'}" + (f" — {reason}" if reason else ""),
            payload={"page": page, "reason": reason},
            severity="info" if allowed else "warning",
        )

    # ── Session summary ───────────────────────────────────────────────────────

    def summarise(self) -> SessionSummary:
        with self._lock:
            events = list(self._events)

        n_uploads   = sum(1 for e in events if e.event_type == EventType.UPLOAD)
        n_analyses  = sum(1 for e in events if e.event_type == EventType.ANALYSIS_COMPLETED)
        n_blocks    = sum(1 for e in events if e.event_type == EventType.GUARD_BLOCKED)
        n_warns     = sum(1 for e in events if e.event_type == EventType.GUARD_WARNED)
        n_errors    = sum(1 for e in events if e.event_type == EventType.ERROR)

        modalities = list({
            e.payload.get("modality", "")
            for e in events if e.event_type == EventType.MODALITY_CLASSIFIED
        } - {""})

        analyses_run = list({
            e.payload.get("analysis", "")
            for e in events if e.event_type == EventType.ANALYSIS_COMPLETED
        } - {""})

        analyses_blocked = list({
            e.payload.get("analysis", "")
            for e in events if e.event_type == EventType.GUARD_BLOCKED
        } - {""})

        health = 1.0
        if n_errors > 0:
            health *= max(0.3, 1.0 - n_errors * 0.2)
        if n_blocks > 3:
            health *= 0.80

        provenance = [
            f"Session: {self.session_id}",
            f"Started: {self._started_at}",
            f"Events: {len(events)}",
            f"Uploads: {n_uploads}, Analyses: {n_analyses}",
            f"Guard blocks: {n_blocks}, Errors: {n_errors}",
        ]

        return SessionSummary(
            session_id=self.session_id,
            started_at=self._started_at,
            ended_at=_now(),
            n_events=len(events),
            n_uploads=n_uploads,
            n_analyses=n_analyses,
            n_guard_blocks=n_blocks,
            n_guard_warnings=n_warns,
            n_errors=n_errors,
            modalities_seen=modalities,
            analyses_run=analyses_run,
            analyses_blocked=analyses_blocked,
            overall_health=round(health, 4),
            provenance=provenance,
        )

    def get_events(self, event_type: Optional[str] = None) -> List[TelemetryEvent]:
        with self._lock:
            if event_type is None:
                return list(self._events)
            return [e for e in self._events if e.event_type == event_type]

    def export_json(self) -> str:
        """Export full event log as JSON string."""
        with self._lock:
            events_raw = [
                {
                    "event_id": e.event_id,
                    "session_id": e.session_id,
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "module": e.module,
                    "description": e.description,
                    "confidence": e.confidence,
                    "duration_ms": e.duration_ms,
                    "severity": e.severity,
                    "payload_keys": list(e.payload.keys()),
                }
                for e in self._events
            ]
        return json.dumps(events_raw, indent=2, default=str)

    # ── SQLite persistence ────────────────────────────────────────────────────

    def _init_db(self):
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    timestamp TEXT,
                    event_type TEXT,
                    module TEXT,
                    description TEXT,
                    confidence REAL,
                    duration_ms REAL,
                    severity TEXT,
                    dataset_hash TEXT,
                    payload TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Telemetry DB init failed: {e} — running in memory-only mode.")
            self._persist = False

    def _write_db(self, event: TelemetryEvent):
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT OR IGNORE INTO telemetry_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.event_id, event.session_id, event.timestamp,
                    event.event_type, event.module, event.description,
                    event.confidence, event.duration_ms, event.severity,
                    event.dataset_hash, json.dumps(event.payload, default=str),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Telemetry DB write failed: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


def hash_dataframe(df: pd.DataFrame) -> str:
    """Anonymised structural hash of a DataFrame (not the content)."""
    sig = f"{df.shape}|{sorted(df.columns.tolist())}|{df.dtypes.to_dict()}"
    return hashlib.sha256(sig.encode()).hexdigest()[:16]


def timed(fn):
    """Decorator to measure function execution duration in ms."""
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        ms = (time.perf_counter() - t0) * 1000
        return result, ms
    return wrapper
