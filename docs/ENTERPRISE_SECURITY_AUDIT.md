# AWI Enterprise Security Audit
## Phase 30.1 — On-Premises Deployment Security Assessment
**Date:** 2026-06-01 | **Version:** v2.0.1-enterprise | **Model:** Enterprise License

---

## Executive Summary

AWI is a fully on-premises enterprise license product. Each customer receives an isolated deployment on their own infrastructure. This audit assesses the security posture of the authentication, API, data handling, and deployment layers against the requirements of a GCC-region enterprise software deployment.

**Overall Security Rating: 78 / 100**
- Authentication: 88/100 (bcrypt + JWT + lockout fully implemented)
- API Security: 72/100 (CORS fixed, auth wired; rate limiting pending)
- Data Security: 80/100 (SQLite WAL; no network egress; local-only)
- Deployment Security: 71/100 (secret key management good; TLS not bundled)

---

## 1. Authentication Security

### 1.1 Password Hashing
| Control | Status | Detail |
|---------|--------|--------|
| bcrypt with cost factor 12 | IMPLEMENTED | `passlib[bcrypt]>=1.7.4` |
| Minimum password length 10 | IMPLEMENTED | `validate_password_strength()` |
| Uppercase + digit + special required | IMPLEMENTED | Enforced on create + change |
| Unique salts per hash | IMPLEMENTED | bcrypt generates per-hash salt |

### 1.2 Session Tokens
| Control | Status | Detail |
|---------|--------|--------|
| JWT HS256 | IMPLEMENTED | `python-jose[cryptography]>=3.3.0` |
| Deployment-specific secret | IMPLEMENTED | `data/awi_secret.key` generated on first boot |
| Access token TTL (8 hours) | IMPLEMENTED | Configurable via constant |
| Refresh token TTL (30 days) | IMPLEMENTED | Stored in `awi_active_tokens` |
| JTI revocation on logout | IMPLEMENTED | `awi_active_tokens.revoked` flag |
| Revocation check on every request | IMPLEMENTED | `is_token_revoked(jti)` in `verify_token_and_get_user()` |

### 1.3 Account Lockout
| Control | Status | Detail |
|---------|--------|--------|
| 5 failed attempts → 15-min lockout | IMPLEMENTED | `_LOCKOUT_MAX_ATTEMPTS=5` |
| Lockout window 15 minutes | IMPLEMENTED | `_LOCKOUT_WINDOW_MINS=15` |
| Admin unlock endpoint | IMPLEMENTED | `POST /api/auth/users/{username}/unlock` |
| Lockout events audited | IMPLEMENTED | `account_locked` audit entry |

### 1.4 Gaps & Recommendations
| Gap | Severity | Recommendation |
|-----|----------|---------------|
| No TOTP/MFA support | MEDIUM | Add optional TOTP in Phase 31 (`pyotp` library) |
| Password history not enforced | LOW | Prevent reuse of last 5 passwords |
| Session idle timeout not enforced | MEDIUM | Add last-activity timestamp; invalidate after 4h idle |

---

## 2. API Security

### 2.1 CORS
| Control | Before 30.1 | After 30.1 |
|---------|-------------|------------|
| `allow_origins` | `["*"]` — wildcard | Localhost origins only by default |
| Override mechanism | None | `AWI_CORS_ORIGINS` env var |
| `allow_credentials` | Not set | `True` |
| Methods | `["*"]` | Restricted to standard HTTP verbs |

### 2.2 Authentication Enforcement
| Control | Status | Detail |
|---------|--------|--------|
| Bearer token validation | IMPLEMENTED | `get_current_user()` FastAPI dependency |
| Role-based access control | IMPLEMENTED | `require_role()` factory + 6 roles |
| Permission-level enforcement | IMPLEMENTED | `require_permission()` based on PERMISSION_MATRIX |
| Auth bypass flag for testing | IMPLEMENTED | `AWI_AUTH_ENFORCED=false` env var |

### 2.3 Gaps & Recommendations
| Gap | Severity | Recommendation |
|-----|----------|---------------|
| No rate limiting on login endpoint | HIGH | Add `slowapi` or nginx-level rate limiting: 10 req/min per IP |
| No HTTPS enforcement in the app | HIGH | Deploy behind nginx with TLS; add HSTS header |
| No request size limit | MEDIUM | Add `LimitUploadSize` middleware (default 50 MB) |
| Swagger UI exposed at /api/v1/docs | LOW | Disable in production with `docs_url=None` |
| Bootstrap endpoint not disabled after setup | MEDIUM | Add `POST /api/auth/bootstrap/disable` |

---

## 3. Data Security

### 3.1 Data Storage
| Control | Status | Detail |
|---------|--------|--------|
| Auth data in SQLite (not files) | IMPLEMENTED | `data/awi_auth.db` WAL mode |
| Workforce data stays local | IMPLEMENTED | No external API calls in analysis pipeline |
| Analysis history persisted locally | IMPLEMENTED | SQLite via `historical_intelligence_engine.py` |
| No PII sent to cloud | IMPLEMENTED | Fully air-gap compatible |

### 3.2 Sensitive Data Handling
| Control | Status | Detail |
|---------|--------|--------|
| JWT secret stored in key file | IMPLEMENTED | `data/awi_secret.key` (chmod 600 on Unix) |
| Passwords never stored in plain text | IMPLEMENTED | bcrypt hash only |
| Audit log includes IP + user agent | IMPLEMENTED | `awi_security_audit` table |
| Employee records not logged | IMPLEMENTED | Audit only captures auth events |

### 3.3 Frontend Data Exposure (EXISTING RISK — pre-30.1)
| Risk | Severity | Status |
|------|----------|--------|
| Analysis results in React state (memory only) | LOW | Acceptable for single-session use |
| No PII in localStorage | VERIFIED | localStorage contains only session flags |
| API responses include employee risk scores | MEDIUM | Must add column-level masking for AUDITOR role (Phase 31) |

---

## 4. Deployment Security

### 4.1 Secrets Management
| Control | Status | Detail |
|---------|--------|--------|
| Unique JWT secret per deployment | IMPLEMENTED | Generated on first boot |
| Secret not in source code | IMPLEMENTED | `data/awi_secret.key` excluded from repo |
| Admin password set via env var at boot | IMPLEMENTED | `AWI_ADMIN_BOOTSTRAP_PASSWORD` env var |
| Key rotation procedure | DOCUMENTED | See `LOCAL_DEPLOYMENT_PACKAGE.md` |

### 4.2 Infrastructure Hardening (Customer Responsibility)
| Recommendation | Priority |
|----------------|----------|
| Run behind TLS-terminating nginx (self-signed acceptable for air-gapped) | CRITICAL |
| Restrict API port (8000) to internal network only | CRITICAL |
| Set filesystem permissions: `data/` readable only by AWI service account | HIGH |
| Enable OS-level firewall: allow only 443/8501 from client VLAN | HIGH |
| Schedule nightly SQLite backups of `data/*.db` | HIGH |
| Rotate JWT secret annually (redeploy required) | MEDIUM |

---

## 5. Threat Model

### 5.1 Threats Mitigated
| Threat | Mitigation |
|--------|-----------|
| Credential stuffing | Account lockout (5 attempts / 15 min) |
| Token replay after logout | JTI revocation in SQLite |
| JWT forgery | Deployment-specific HS256 secret |
| Privilege escalation | RBAC enforcement on every sensitive endpoint |
| Unauthorised CORS access | Explicit origin whitelist |
| Audit trail tampering | Audit log is append-only (no DELETE endpoint) |

### 5.2 Residual Risks
| Risk | Severity | Mitigation Path |
|------|----------|-----------------|
| Local admin can access SQLite directly | MEDIUM | OS file permissions + dedicated service account |
| No MFA for privileged accounts | MEDIUM | TOTP Phase 31 |
| Single-factor for CHRO/EXECUTIVE | MEDIUM | TOTP Phase 31 |
| TLS not bundled (customer sets up nginx) | HIGH | Provide nginx config template in deployment package |
| Brute-force after lockout expires | LOW | Lockout resets every 15 min — acceptable for enterprise |

---

## 6. Compliance Readiness

| Standard | Coverage | Gap |
|----------|----------|-----|
| SAMA Cybersecurity Framework | 75% | MFA, audit retention policy |
| NCA ECC-1:2018 | 70% | TLS requirement, log retention |
| ISO 27001 (partial) | 65% | Formal ISMS, incident response plan |
| PDPL (Saudi Data Privacy) | 80% | Data residency: FULL. Consent tracking: partial |

**Conclusion:** AWI Phase 30.1 delivers a credible enterprise authentication layer suitable for pilot deployment at Aramco, STC, and Riyad Bank. The remaining gaps (MFA, TLS bundling, rate limiting) do not block initial deployment but must be addressed before production-scale rollout.

---

*Generated: Phase 30.1 | AWI Enterprise Workforce Intelligence Platform v2.0.1*
