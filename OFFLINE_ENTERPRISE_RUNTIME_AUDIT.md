# Offline Enterprise Runtime Audit — Phase 11

**Date:** 2026-05-21  
**Component:** `LocalEnterpriseRuntime`  
**Module:** `backend/core/local_enterprise_runtime.py`

---

## 1. Architecture Overview

`LocalEnterpriseRuntime` is the platform's local execution environment manager. It enforces offline-first operation, creates per-tenant directory trees, manages an append-only audit log, and provides a bounded in-memory report cache.

```
LocalEnterpriseRuntime (singleton)
├── OfflineModeGuard        — blocks all non-loopback network calls
├── _BoundedCache (LRU)     — max 50 entries, thread-safe
├── _tenants dict           — TenantRuntimeContext per tenant
└── Audit JSONL writer      — append-only, per-tenant, PII-stripped
```

All state is local-filesystem-only. No database, no network, no cloud dependency.

---

## 2. Directory Layout

For each tenant, the runtime creates and manages:

```
data/enterprise/
└── {tenant_id}/
    ├── reports/        — generated HTML/PDF reports
    ├── exports/        — audit packages, ZIP exports
    ├── audit_logs/     — audit.jsonl (append-only JSONL event log)
    ├── cache/          — temporary computation results
    └── uploads/        — ingested (anonymised) datasets
```

Base directory defaults to `data/enterprise/` unless overridden by the `AWI_DATA_DIR` environment variable.

Directories are created with `mkdir(parents=True, exist_ok=True)` — safe to call if already present.

---

## 3. Offline Mode Guard Integration

On `start()`, the runtime immediately installs `OfflineModeGuard` before any other operation:

```python
def start(self) -> None:
    if self._started:
        return
    install_offline_guard()          # Must be first
    self._base_dir.mkdir(...)
    self._started_at = datetime.now(timezone.utc).isoformat()
    self._started = True
```

**OfflineModeGuard mechanism:**
- Patches `socket.getaddrinfo` at the socket module level
- Intercepts all DNS resolution attempts from any HTTP library
- Blocks any non-loopback hostname (rejects everything except `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`)
- Raises `OfflinePolicyViolation(RuntimeError)` on blocked attempts
- All violations logged at WARNING level with host and port

**Status check:** `status()` reports `offline_guard_active: bool` via `is_offline_guard_active()`. If the guard is not active when `status()` is called, a warning is appended:
```
"OFFLINE_GUARD_NOT_ACTIVE: External network calls are not blocked."
```

---

## 4. Tenant Isolation

### 4.1 Tenant ID Validation

All tenant IDs are validated before any directory creation:

| Rule | Detail |
|------|--------|
| Non-empty | Rejects empty or whitespace-only strings |
| Minimum length | ≥ 2 characters |
| Maximum length | ≤ 64 characters |
| Path traversal block | Rejects any ID containing `".."`, `"/"`, or `"\\"` |
| Regex format | `^[a-z0-9][a-z0-9\-]{0,62}[a-z0-9]$` |

Path traversal rejection:
```python
if ".." in tenant_id or "/" in tenant_id or "\\" in tenant_id:
    raise ValueError(f"tenant_id contains path traversal characters: {tenant_id!r}")
```

Test 14 confirms `"../../../etc"` and `"tenant/../../secret"` both raise `ValueError`.

### 4.2 Directory Isolation

Each tenant's context is scoped to `{base_dir}/{tenant_id}/`. The runtime never constructs cross-tenant paths. `_tenants` dict is locked with a dedicated `threading.Lock()` for concurrent access safety.

### 4.3 Cache Isolation

Cache keys use format `"{tenant_id}||{sha256(report_key)[:16]}"`:
```python
def _cache_key(self, tenant_id: str, report_key: str) -> str:
    key_hash = hashlib.sha256(report_key.encode()).hexdigest()[:16]
    return f"{tenant_id}||{key_hash}"
```

`clear_tenant_cache(tenant_id)` rebuilds the cache excluding all keys starting with `"{tenant_id}||"`:
```python
prefix = f"{tenant_id}||"
for k, v in list(self._cache._store.items()):
    if not k.startswith(prefix):
        new_cache.put(k, v)
```

This ensures clearing one tenant's cache never affects another tenant's cached reports.

---

## 5. Bounded LRU Cache

`_BoundedCache` is an in-memory `OrderedDict`-backed LRU cache:

| Property | Value |
|----------|-------|
| Max entries | 50 |
| Eviction policy | LRU (least-recently-used evicted when full) |
| Thread safety | `threading.Lock()` on all operations |
| Key format | `"{tenant_id}||{sha256[:16]}"` |

Operations:
- `get(key)` — moves to end (marks as recently used), returns value or None
- `put(key, value)` — moves to end if existing; evicts oldest if `len > max`
- `clear()` — empties all entries
- `clear_tenant_cache()` — selective clear by tenant prefix

---

## 6. Audit Logging

### 6.1 Log Format

Audit events are written as JSONL (one JSON object per line) to `{tenant_id}/audit_logs/audit.jsonl`:

```json
{
  "timestamp": "2026-05-21T10:23:45.123456+00:00",
  "tenant_id": "riyadh-industrial",
  "event_type": "model_inference",
  "payload": {"department": "IT", "row_count": 500},
  "offline_mode": true
}
```

All timestamps are UTC ISO 8601 (`datetime.now(timezone.utc).isoformat()`).

### 6.2 PII Stripping

Before writing, the payload is passed through `_sanitise_payload()`:

**Always-stripped fields** (hardcoded set regardless of caller instruction):
```
national_id, iqama, email, phone, mobile,
employee_id, emp_id, full_name, password, token
```

**Caller-specified sensitive fields:** Additional fields passed via `sensitive_fields` parameter.

Stripped values are replaced with `"[REDACTED]"`. Field names are compared case-insensitively.

```python
return {
    k: "[REDACTED]" if k.lower() in all_sensitive else v
    for k, v in payload.items()
}
```

### 6.3 Append-Only Guarantee

The audit log file is opened in append mode (`"a"`) on every write:
```python
with open(log_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

No delete, no overwrite, no truncation. Failed writes return `False` and log at ERROR level without raising (audit failures must not crash the main processing pipeline).

---

## 7. Runtime Status

`status()` returns a `RuntimeStatus` dataclass visible to admin and trust panels:

| Field | Type | Description |
|-------|------|-------------|
| `is_online` | bool | Always `False` (platform is always offline) |
| `offline_guard_active` | bool | Whether `OfflineModeGuard` is installed |
| `base_directory` | str | Absolute path to `data/enterprise/` |
| `tenant_count` | int | Number of tenants with active contexts |
| `active_tenants` | list[str] | List of tenant IDs with created contexts |
| `cache_entry_count` | int | Current entries in the LRU cache |
| `audit_log_count` | int | Total audit events written this session |
| `started_at` | str | UTC ISO 8601 timestamp of `start()` call |
| `warnings` | list[str] | Non-fatal policy warnings (e.g., guard not active) |

---

## 8. Singleton Pattern

`LocalEnterpriseRuntime` is a class-level singleton:
```python
@classmethod
def get_instance(cls, base_dir=None) -> "LocalEnterpriseRuntime":
    with cls._lock:
        if cls._instance is None:
            cls._instance = cls(base_dir=base_dir)
        return cls._instance
```

Module-level convenience:
```python
def get_runtime(base_dir=None) -> LocalEnterpriseRuntime:
    runtime = LocalEnterpriseRuntime.get_instance(base_dir=base_dir)
    if not runtime._started:
        runtime.start()
    return runtime
```

**Test isolation:** Tests reset `LocalEnterpriseRuntime._instance = None` in `teardown_method()` and also uninstall `OfflineModeGuard` to prevent global state contamination between tests.

---

## 9. Test Coverage (Phase 11 Tests 9–14)

| Test | What is verified |
|------|----------------|
| 9 | `start()` installs offline guard; base directory exists |
| 10 | `get_tenant_context()` creates all 5 subdirs: reports, exports, audit_logs, cache, uploads |
| 11 | `write_audit_event()` strips `national_id` and `email` to `[REDACTED]`; `department` and `row_count` preserved |
| 12 | Cache tenant isolation: clearing tenant-a does not affect tenant-b cached reports |
| 13 | `status().is_online` is always `False`; `offline_guard_active` is `True` after start |
| 14 | Path traversal tenant IDs (`../../../etc`, `tenant/../../secret`) raise `ValueError` |

---

## 10. Governance Non-Negotiables

| Requirement | Implementation |
|------------|---------------|
| No network calls | `OfflineModeGuard` installed before any tenant operation |
| No cross-tenant data access | Directory isolation + cache key prefix isolation |
| No PII in audit logs | `_sanitise_payload()` with always-strip set |
| Append-only audit trail | File opened in `"a"` mode exclusively |
| Bounded memory | LRU cache capped at 50 entries |
| Path traversal blocked | `".."`, `"/"`, `"\\"` rejection before `mkdir()` |
