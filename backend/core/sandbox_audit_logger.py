"""
Sandbox Execution Audit Logger — Phase 43.

Every piece of code the sandboxed-execution feature runs is logged here,
append-only, BEFORE execution starts — so the audit trail exists even if the
sandboxed process crashes, is killed for a resource violation, or the whole
backend process dies mid-run. Mirrors the exact JSONL append-only convention
already established by backend/core/governance_logger.py (logs/*.jsonl,
dataclass event -> json.dumps -> append), rather than inventing a new
logging pattern.

GOVERNANCE NOTE: this log intentionally stores the FULL generated code text
and the FULL sandbox result (stdout/stderr/exit reason) — unlike
audit_logger.py's AuditLogEntry, which explicitly forbids raw data. That's
correct here: the "data" being protected is the uploaded file's contents,
which never appear in this log (only the code that operated on them, and
file *metadata* like row/sheet counts in the diff summary). The generated
code is the one thing this platform's whole session has insisted must always
be inspectable after the fact, precisely because it is LLM-authored and not
a fixed, reviewed function like every other registered tool.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "sandbox_execution.jsonl"


@dataclass
class SandboxExecutionEvent:
    run_id: str
    timestamp: float
    tenant_id: str
    user_request: str            # the natural-language instruction that produced this code
    generated_code: str          # the FULL code the sandbox was asked to run
    input_filename: str
    outcome: str                 # "success" | "code_error" | "sandbox_violation" | "timeout" | "resource_exceeded"
    exit_reason: str             # human-readable reason (e.g. "OFFLINE_POLICY_VIOLATION: ...", "MemoryError", "wall-clock timeout (30s)")
    stdout_excerpt: str          # first 4000 chars of captured stdout
    stderr_excerpt: str          # first 4000 chars of captured stderr
    duration_ms: float
    peak_memory_mb: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SandboxAuditLogger:
    """Append-only JSONL logger for every sandboxed code-execution attempt."""

    def __init__(self, log_path: Optional[Path] = None):
        self._path = log_path or _LOG_PATH
        self._events: List[SandboxExecutionEvent] = []
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def new_run_id(self) -> str:
        return str(uuid.uuid4())

    def log_submission(
        self,
        run_id: str,
        tenant_id: str,
        user_request: str,
        generated_code: str,
        input_filename: str,
    ) -> None:
        """Logged BEFORE execution — guarantees an audit trail even if the
        sandbox process is killed and never reports back."""
        self._emit(SandboxExecutionEvent(
            run_id=run_id,
            timestamp=time.time(),
            tenant_id=tenant_id,
            user_request=user_request,
            generated_code=generated_code,
            input_filename=input_filename,
            outcome="submitted",
            exit_reason="",
            stdout_excerpt="",
            stderr_excerpt="",
            duration_ms=0.0,
        ))

    def log_result(
        self,
        run_id: str,
        tenant_id: str,
        user_request: str,
        generated_code: str,
        input_filename: str,
        outcome: str,
        exit_reason: str,
        stdout: str,
        stderr: str,
        duration_ms: float,
        peak_memory_mb: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._emit(SandboxExecutionEvent(
            run_id=run_id,
            timestamp=time.time(),
            tenant_id=tenant_id,
            user_request=user_request,
            generated_code=generated_code,
            input_filename=input_filename,
            outcome=outcome,
            exit_reason=exit_reason,
            stdout_excerpt=stdout[:4000],
            stderr_excerpt=stderr[:4000],
            duration_ms=duration_ms,
            peak_memory_mb=peak_memory_mb,
            details=details or {},
        ))

    def _emit(self, event: SandboxExecutionEvent) -> None:
        self._events.append(event)
        try:
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
        except Exception:
            pass

    def recent_events(self, n: int = 50) -> List[SandboxExecutionEvent]:
        return self._events[-n:]


_logger: Optional[SandboxAuditLogger] = None


def get_sandbox_audit_logger() -> SandboxAuditLogger:
    global _logger
    if _logger is None:
        _logger = SandboxAuditLogger()
    return _logger
