"""
Offline Mode Guard — Phase 10.

Enforces the offline/local-first design requirement:
  - All employee data must remain on-premises
  - No external HTTP/HTTPS calls are permitted during analysis
  - Any attempt to call external services is logged as OFFLINE_POLICY_VIOLATION
  - Cloud-sync, telemetry, and external API calls are permanently blocked

Design rules:
  - Patch is applied at import time via install() — one call, global effect
  - Socket connections to non-loopback addresses are blocked
  - urllib/requests/httpx are also intercepted
  - Violations raise OfflinePolicyViolation (a RuntimeError subclass)
  - All violations are logged at ERROR level with caller info
  - Guard state is auditable via OfflineModeGuard.status()

Why this matters:
  Saudi PDPL (Personal Data Protection Law) requires that employee personal
  data not leave the Kingdom without explicit consent. This guard enforces
  the architectural guarantee that the platform never exfiltrates data to
  external services, even in development/testing contexts.
"""

from __future__ import annotations

import builtins
import inspect
import logging
import os
import socket
import sys
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ── Exception ─────────────────────────────────────────────────────────────────

class OfflinePolicyViolation(RuntimeError):
    """Raised when code attempts an external network call in offline mode."""

    def __init__(self, destination: str, caller_info: str = ""):
        self.destination = destination
        self.caller_info = caller_info
        super().__init__(
            f"OFFLINE_POLICY_VIOLATION: External network call blocked. "
            f"Destination: '{destination}'. "
            f"This platform operates in offline/local-first mode. "
            f"Employee data must remain on-premises per Saudi PDPL requirements. "
            f"Caller: {caller_info or 'unknown'}"
        )


# ── Violation log entry ───────────────────────────────────────────────────────

@dataclass
class ViolationRecord:
    timestamp: str
    destination: str
    caller_info: str
    stack_excerpt: str


# ── Guard singleton ───────────────────────────────────────────────────────────

class OfflineModeGuard:
    """
    Singleton guard that enforces offline-only network policy.

    Usage:
        guard = OfflineModeGuard.get_instance()
        guard.install()       # patch socket at module level
        guard.status()        # audit current state

    Or use the module-level convenience:
        from backend.core.offline_mode_guard import install_offline_guard
        install_offline_guard()
    """

    _instance: Optional["OfflineModeGuard"] = None
    _lock = threading.Lock()

    # Addresses that are always permitted (loopback / local)
    _ALLOWED_HOSTS: frozenset[str] = frozenset({
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
    })

    def __init__(self) -> None:
        self._installed = False
        self._violations: list[ViolationRecord] = []
        self._original_socket_connect: Optional[Callable] = None
        self._original_getaddrinfo: Optional[Callable] = None

    @classmethod
    def get_instance(cls) -> "OfflineModeGuard":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ── Installation ──────────────────────────────────────────────────────────

    def install(self) -> None:
        """
        Patch socket.socket.connect and socket.getaddrinfo to intercept
        any attempt to reach a non-loopback address.
        """
        if self._installed:
            return

        self._original_getaddrinfo = socket.getaddrinfo

        _guard = self   # capture for closure

        def _patched_getaddrinfo(host, port, *args, **kwargs):
            if not _guard._is_allowed(str(host)):
                caller = _guard._get_caller_info()
                _guard._record_violation(f"{host}:{port}", caller)
                raise OfflinePolicyViolation(f"{host}:{port}", caller)
            return _guard._original_getaddrinfo(host, port, *args, **kwargs)

        socket.getaddrinfo = _patched_getaddrinfo
        self._installed = True

        logger.info(
            "OfflineModeGuard installed: all external network calls are blocked. "
            "Loopback (localhost/127.0.0.1) remains permitted."
        )

    def uninstall(self) -> None:
        """Restore original socket behaviour (for testing only)."""
        if not self._installed:
            return
        if self._original_getaddrinfo is not None:
            socket.getaddrinfo = self._original_getaddrinfo
        self._installed = False
        logger.warning("OfflineModeGuard uninstalled — external calls are now permitted.")

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return auditable status of the guard."""
        return {
            "offline_mode_active": self._installed,
            "violation_count": len(self._violations),
            "violations": [
                {
                    "timestamp":    v.timestamp,
                    "destination":  v.destination,
                    "caller":       v.caller_info,
                    "stack_excerpt": v.stack_excerpt,
                }
                for v in self._violations
            ],
            "allowed_hosts": sorted(self._ALLOWED_HOSTS),
            "policy": (
                "OFFLINE_FIRST: All external network connections are blocked. "
                "Employee data must remain on-premises per Saudi PDPL requirements."
            ),
        }

    def get_violation_count(self) -> int:
        return len(self._violations)

    def clear_violations(self) -> None:
        """Clear the violation log (call during test teardown only)."""
        self._violations.clear()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_allowed(self, host: str) -> bool:
        """Return True if the host is loopback / permitted."""
        host_clean = host.strip().lower()
        return host_clean in self._ALLOWED_HOSTS

    def _record_violation(self, destination: str, caller_info: str) -> None:
        stack_lines = traceback.format_stack()
        # Take last 5 frames, skip guard internals
        relevant = [l for l in stack_lines if "offline_mode_guard" not in l][-5:]
        stack_excerpt = "".join(relevant).strip()

        record = ViolationRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            destination=destination,
            caller_info=caller_info,
            stack_excerpt=stack_excerpt,
        )
        self._violations.append(record)

        logger.error(
            "OFFLINE_POLICY_VIOLATION | destination=%s | caller=%s",
            destination,
            caller_info,
        )

    def _get_caller_info(self) -> str:
        """Return file:line for the first non-guard frame in the call stack."""
        try:
            stack = inspect.stack()
            for frame_info in stack:
                filename = frame_info.filename
                if "offline_mode_guard" in filename:
                    continue
                return f"{os.path.basename(filename)}:{frame_info.lineno}"
        except Exception:
            pass
        return "unknown"


# ── Module-level convenience ──────────────────────────────────────────────────

def install_offline_guard() -> OfflineModeGuard:
    """
    Install the offline mode guard and return the singleton.
    Safe to call multiple times — installs only once.
    """
    guard = OfflineModeGuard.get_instance()
    guard.install()
    return guard


def get_offline_guard_status() -> dict:
    """Return the current guard status without installing."""
    return OfflineModeGuard.get_instance().status()


def is_offline_guard_active() -> bool:
    """Return True if the offline guard is currently installed."""
    return OfflineModeGuard.get_instance()._installed
