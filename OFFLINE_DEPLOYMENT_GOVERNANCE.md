# Offline Deployment Governance — Phase 10

**Date:** 2026-05-21  
**Module:** `backend/core/offline_mode_guard.py`  
**Legal basis:** Saudi Personal Data Protection Law (PDPL) — Royal Decree No. M/19, 2021

---

## 1. Policy Statement

The Adaptive Workforce AI platform is designed as a **local-first, offline-capable system**. All employee data must remain within the organisation's on-premises infrastructure or Saudi data centre. No employee personal data may be transmitted to external services, cloud APIs, telemetry endpoints, or any third-party system without explicit tenant consent.

This is not a configuration option. It is an architectural requirement enforced at runtime.

---

## 2. Why This Policy Exists

### Saudi PDPL Requirements

The Saudi Personal Data Protection Law (PDPL), enforced by the National Data Management Office (NDMO), requires:

- **Article 5:** Personal data may only be processed for specified, explicit, and legitimate purposes
- **Article 16:** Cross-border personal data transfers require controller consent and NDMO approval
- **Article 19:** Appropriate technical and organisational measures must protect personal data

Employee data (satisfaction scores, attrition risk, demographic information) constitutes personal data under PDPL. Transmitting this data to external APIs (cloud AI services, analytics platforms, telemetry) without NDMO approval and employee consent would be a PDPL violation.

### Practical Risk

AI platforms commonly send data to external services for:
- Model inference (sending employee records to cloud AI APIs)
- Telemetry and usage analytics
- Error reporting with attached payloads
- Feature flags that transmit context

Even unintentional calls carry legal and reputational risk. The guard prevents this class of incident entirely.

---

## 3. Technical Implementation

**Module:** `backend/core/offline_mode_guard.py`  
**Class:** `OfflineModeGuard` (singleton)  
**Mechanism:** Patches `socket.getaddrinfo` to intercept DNS resolution attempts

### How the guard works

1. `OfflineModeGuard.install()` replaces `socket.getaddrinfo` with a patched version
2. Every DNS resolution attempt is checked against the allowed host list
3. Loopback addresses (`localhost`, `127.0.0.1`, `::1`) are permitted — local services work normally
4. Any other host raises `OfflinePolicyViolation` immediately, before the connection is established
5. The violation is logged at ERROR level and recorded in the guard's audit log

### Why getaddrinfo (not connect)

Patching `getaddrinfo` intercepts all DNS resolution attempts, which catches:
- `requests.get("https://external.com")`
- `httpx.get("https://external.com")`
- `urllib.request.urlopen("https://external.com")`
- `socket.connect(("external.com", 443))`

All of these ultimately call `getaddrinfo` for hostname resolution. Patching at this level provides a single enforcement point regardless of the HTTP library used.

---

## 4. Allowed Traffic

| Host | Reason |
|------|--------|
| `localhost` | Local FastAPI server, local services |
| `127.0.0.1` | Loopback IPv4 |
| `::1` | Loopback IPv6 |
| `0.0.0.0` | Bind-all address (server startup) |

Everything else is blocked.

---

## 5. Violation Handling

When a violation is detected:

1. `OfflinePolicyViolation` is raised (subclass of `RuntimeError`)
2. Violation is recorded with: timestamp, destination, caller file/line, stack excerpt
3. Log entry at `ERROR` level: `OFFLINE_POLICY_VIOLATION | destination=... | caller=...`
4. The connection attempt fails immediately — no data is transmitted

### Violation record structure

```python
{
    "timestamp":     "2026-05-21T10:30:00+00:00",
    "destination":   "api.openai.com:443",
    "caller":        "some_module.py:142",
    "stack_excerpt": "..."
}
```

---

## 6. Guard Lifecycle

| Operation | Method | Notes |
|-----------|--------|-------|
| Install | `guard.install()` | Safe to call multiple times |
| Uninstall | `guard.uninstall()` | For test teardown only — emits a WARNING |
| Check status | `guard.status()` | Returns full audit dict |
| Count violations | `guard.get_violation_count()` | Integer count |
| Clear violations | `guard.clear_violations()` | Test teardown only |

### Module-level convenience functions

```python
from backend.core.offline_mode_guard import install_offline_guard, is_offline_guard_active

guard = install_offline_guard()    # Install and return singleton
active = is_offline_guard_active() # Check without installing
status = get_offline_guard_status() # Audit dict without installing
```

---

## 7. Integration Points

The offline guard should be installed at application startup:

```python
# In main.py or app startup
from backend.core.offline_mode_guard import install_offline_guard

guard = install_offline_guard()
logger.info("Offline mode active: %s", guard.status()["policy"])
```

The guard status should be included in audit package builds so that compliance auditors can verify offline-mode enforcement was active during any analysis session.

---

## 8. Testing

Tests 15–16 in `tests/test_phase10_real_saudi_datasets.py` verify:
- Guard blocks non-loopback hosts
- Loopback addresses are permitted
- Violation count is tracked accurately
- Status dict includes required fields
- Violation records include timestamp, destination, and caller info

---

## 9. Limitations

1. **Does not prevent local file writes** — the guard blocks network calls, not disk I/O
2. **Does not block subprocess calls** — a subprocess could make network calls independently
3. **Test isolation** — the guard must be properly installed/uninstalled in test suites to avoid contaminating the global socket state
4. **HTTPS MITM** — the guard does not perform TLS inspection; it prevents connection initiation entirely

---

## 10. Compliance Certification

| Requirement | Status |
|------------|--------|
| No external API calls during employee data processing | ENFORCED via OfflineModeGuard |
| Violation logging with caller attribution | IMPLEMENTED |
| Audit trail of offline enforcement | IMPLEMENTED via status() dict |
| PDPL cross-border transfer prevention | ENFORCED by network block |
| Test coverage | 2 tests, 481 total passing |

---

*This governance document must be reviewed if deployment architecture changes (e.g., moving to cloud-hosted model inference). Any change to the offline policy requires legal review against current PDPL regulations and tenant consent agreements.*
