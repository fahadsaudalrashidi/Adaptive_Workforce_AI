"""
Local Enterprise Runtime — Phase 11.

Manages the fully local execution environment for the Adaptive Workforce AI platform.

Responsibilities:
  - Configure local data directories (audit logs, exports, reports, cache)
  - Enforce offline-first operation via OfflineModeGuard integration
  - Provide per-tenant execution context with directory isolation
  - Manage local report caching (in-memory, bounded size)
  - Generate health status for admin/executive trust panels
  - Log runtime startup, directory creation, and policy enforcement

Design rules:
  - All paths are local filesystem paths (no UNC/cloud mount paths)
  - No network calls ever issued from this module
  - Tenant directories are isolated (no cross-tenant path traversal)
  - Audit logs are append-only (no delete, no overwrite)
  - Cache is bounded (max 50 entries, LRU eviction)
  - Runtime status is always auditable via .status()
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.core.offline_mode_guard import install_offline_guard, is_offline_guard_active

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_SAFE_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,62}[a-z0-9]$")
_MAX_CACHE_ENTRIES = 50
_DEFAULT_BASE_DIR  = Path(os.environ.get("AWI_DATA_DIR", "data/enterprise"))


# ── Directory layout ──────────────────────────────────────────────────────────
# For each tenant:
#   <base>/<tenant_id>/
#     reports/        — generated HTML/PDF reports
#     exports/        — audit packages, ZIP exports
#     audit_logs/     — append-only JSONL event logs
#     cache/          — temporary computation results
#     uploads/        — ingested (anonymised) datasets

_TENANT_SUBDIRS = ["reports", "exports", "audit_logs", "cache", "uploads"]


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class TenantRuntimeContext:
    tenant_id: str
    base_dir: Path
    reports_dir: Path
    exports_dir: Path
    audit_logs_dir: Path
    cache_dir: Path
    uploads_dir: Path
    created_at: str
    directories_ready: bool


@dataclass
class RuntimeStatus:
    is_online: bool                     # always False (offline-first)
    offline_guard_active: bool
    base_directory: str
    tenant_count: int
    active_tenants: list[str]
    cache_entry_count: int
    audit_log_count: int
    started_at: str
    warnings: list[str]


# ── Bounded LRU cache ─────────────────────────────────────────────────────────

class _BoundedCache:
    def __init__(self, max_size: int = _MAX_CACHE_ENTRIES):
        self._store: OrderedDict[str, object] = OrderedDict()
        self._max = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[object]:
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def put(self, key: str, value: object) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = value
            if len(self._store) > self._max:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# ── Runtime singleton ─────────────────────────────────────────────────────────

class LocalEnterpriseRuntime:
    """
    Manages the local execution environment for the platform.

    Usage:
        runtime = LocalEnterpriseRuntime(base_dir=Path("data/enterprise"))
        runtime.start()
        ctx = runtime.get_tenant_context("riyadh-industrial")
        status = runtime.status()
    """

    _instance: Optional["LocalEnterpriseRuntime"] = None
    _lock = threading.Lock()

    def __init__(self, base_dir: Optional[Path] = None):
        self._base_dir = base_dir or _DEFAULT_BASE_DIR
        self._tenants: dict[str, TenantRuntimeContext] = {}
        self._cache = _BoundedCache()
        self._audit_log_count = 0
        self._started_at: Optional[str] = None
        self._started = False
        self._tenant_lock = threading.Lock()

    @classmethod
    def get_instance(cls, base_dir: Optional[Path] = None) -> "LocalEnterpriseRuntime":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(base_dir=base_dir)
            return cls._instance

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Start the runtime: install offline guard, create base directory,
        verify configuration.
        """
        if self._started:
            return

        # Offline guard — must be installed first
        install_offline_guard()
        logger.info("LocalEnterpriseRuntime: offline guard installed")

        # Ensure base directory exists
        self._base_dir.mkdir(parents=True, exist_ok=True)
        logger.info("LocalEnterpriseRuntime: base directory ready at %s", self._base_dir)

        self._started_at = datetime.now(timezone.utc).isoformat()
        self._started = True
        logger.info("LocalEnterpriseRuntime started at %s", self._started_at)

    # ── Tenant context ─────────────────────────────────────────────────────────

    def get_tenant_context(self, tenant_id: str) -> TenantRuntimeContext:
        """
        Get or create a runtime context for a tenant.
        Creates the tenant's directory tree on first call.
        """
        if not self._started:
            self.start()

        self._validate_tenant_id(tenant_id)

        with self._tenant_lock:
            if tenant_id in self._tenants:
                return self._tenants[tenant_id]

            ctx = self._create_tenant_context(tenant_id)
            self._tenants[tenant_id] = ctx
            return ctx

    def _create_tenant_context(self, tenant_id: str) -> TenantRuntimeContext:
        tenant_base = self._base_dir / tenant_id

        dirs = {
            sub: tenant_base / sub
            for sub in _TENANT_SUBDIRS
        }

        all_ready = True
        for sub, path in dirs.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning("Could not create tenant dir %s: %s", path, e)
                all_ready = False

        ctx = TenantRuntimeContext(
            tenant_id=tenant_id,
            base_dir=tenant_base,
            reports_dir=dirs["reports"],
            exports_dir=dirs["exports"],
            audit_logs_dir=dirs["audit_logs"],
            cache_dir=dirs["cache"],
            uploads_dir=dirs["uploads"],
            created_at=datetime.now(timezone.utc).isoformat(),
            directories_ready=all_ready,
        )
        logger.info("Tenant context created: %s (dirs_ready=%s)", tenant_id, all_ready)
        return ctx

    # ── Audit logging ──────────────────────────────────────────────────────────

    def write_audit_event(
        self,
        tenant_id: str,
        event_type: str,
        payload: dict,
        sensitive_fields: Optional[list[str]] = None,
    ) -> bool:
        """
        Append an audit event to the tenant's audit log.
        Automatically strips sensitive fields before writing.
        Returns True on success.
        """
        try:
            ctx = self.get_tenant_context(tenant_id)
            safe_payload = self._sanitise_payload(payload, sensitive_fields or [])
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tenant_id": tenant_id,
                "event_type": event_type,
                "payload": safe_payload,
                "offline_mode": True,
            }
            log_path = ctx.audit_logs_dir / "audit.jsonl"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._audit_log_count += 1
            return True
        except Exception as exc:
            logger.error("Audit write failed for tenant %s: %s", tenant_id, exc)
            return False

    # ── Report caching ─────────────────────────────────────────────────────────

    def cache_report(self, tenant_id: str, report_key: str, content: str) -> str:
        """
        Store a generated report in the bounded cache.
        Returns the cache key.
        """
        key = self._cache_key(tenant_id, report_key)
        self._cache.put(key, content)
        return key

    def get_cached_report(self, tenant_id: str, report_key: str) -> Optional[str]:
        """Retrieve a cached report, or None if not present."""
        key = self._cache_key(tenant_id, report_key)
        return self._cache.get(key)

    def clear_tenant_cache(self, tenant_id: str) -> None:
        """Clear all cached entries for a tenant (resets demo safely)."""
        prefix = f"{tenant_id}||"
        new_cache = _BoundedCache(self._cache._max)
        with self._cache._lock:
            for k, v in list(self._cache._store.items()):
                if not k.startswith(prefix):
                    new_cache.put(k, v)
        self._cache = new_cache

    # ── Status ─────────────────────────────────────────────────────────────────

    def status(self) -> RuntimeStatus:
        warnings: list[str] = []
        if not is_offline_guard_active():
            warnings.append(
                "OFFLINE_GUARD_NOT_ACTIVE: External network calls are not blocked. "
                "Call start() or install_offline_guard() before processing employee data."
            )
        if not self._started:
            warnings.append("Runtime has not been started. Call start() first.")

        return RuntimeStatus(
            is_online=False,
            offline_guard_active=is_offline_guard_active(),
            base_directory=str(self._base_dir.absolute()) if self._base_dir else "",
            tenant_count=len(self._tenants),
            active_tenants=list(self._tenants.keys()),
            cache_entry_count=len(self._cache),
            audit_log_count=self._audit_log_count,
            started_at=self._started_at or "",
            warnings=warnings,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _validate_tenant_id(self, tenant_id: str) -> None:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        if len(tenant_id) < 2:
            raise ValueError("tenant_id must be at least 2 characters")
        if len(tenant_id) > 64:
            raise ValueError("tenant_id must not exceed 64 characters")
        if ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
            raise ValueError(f"tenant_id contains path traversal characters: {tenant_id!r}")

    def _cache_key(self, tenant_id: str, report_key: str) -> str:
        # Use "tenant_id||<hash>" so prefix filtering in clear_tenant_cache works
        key_hash = hashlib.sha256(report_key.encode()).hexdigest()[:16]
        return f"{tenant_id}||{key_hash}"

    def _sanitise_payload(self, payload: dict, sensitive_fields: list[str]) -> dict:
        _ALWAYS_STRIP = {
            "national_id", "iqama", "email", "phone", "mobile",
            "employee_id", "emp_id", "full_name", "password", "token",
        }
        all_sensitive = _ALWAYS_STRIP | set(f.lower() for f in sensitive_fields)
        return {
            k: "[REDACTED]" if k.lower() in all_sensitive else v
            for k, v in payload.items()
        }


# ── Module-level convenience ──────────────────────────────────────────────────

def get_runtime(base_dir: Optional[Path] = None) -> LocalEnterpriseRuntime:
    """Return the singleton runtime, starting it if not yet started."""
    runtime = LocalEnterpriseRuntime.get_instance(base_dir=base_dir)
    if not runtime._started:
        runtime.start()
    return runtime
