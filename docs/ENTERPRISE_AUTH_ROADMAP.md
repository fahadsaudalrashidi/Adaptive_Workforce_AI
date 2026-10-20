# AWI Enterprise Authentication Roadmap
## SSO, RBAC, Audit, and Identity Architecture

**Version:** v2.0.0-enterprise  
**Date:** 2026-06-01  
**Status:** Architecture Complete — Implementation Phase 31

---

## Current State (Phase 30)

AWI Phase 30 operates with a **single-tenant, session-based** local access model:
- No user authentication required for local on-premises deployment
- Tenant ID enforces data isolation between organisations
- All sessions are local — no token exchange with external identity providers
- Governance audit trail exists per session (tenant_audit_log)

This is appropriate for:
- Single-user CHRO/HR Analytics laptop deployment
- Closed-network government lab environments
- Academic and pilot evaluation contexts

**Phase 31 will implement full enterprise authentication.** This document defines the target architecture.

---

## Target Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  AWI Identity Layer (Phase 31)                                    │
│                                                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │  SSO Gateway    │  │  RBAC Engine     │  │  Audit Logger  │  │
│  │  (SAML 2.0 /   │  │  (Role resolver  │  │  (Immutable    │  │
│  │   OAuth 2.0 /  │  │   + Permission   │  │   per-event    │  │
│  │   Entra ID)    │  │   enforcer)      │  │   SQLite log)  │  │
│  └─────────────────┘  └──────────────────┘  └────────────────┘  │
│           │                    │                    │            │
│           ▼                    ▼                    ▼            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AWI API Gateway (FastAPI)                                │   │
│  │  Request → Authenticate → Authorize → Audit → Execute    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Single Sign-On (SSO) Integration

### 1.1 Supported Identity Providers

| Provider | Protocol | Priority | Target Clients |
|---|---|---|---|
| **Microsoft Entra ID** (Azure AD) | SAML 2.0 / OAuth 2.0 | P0 | Saudi enterprise, banks, telecom |
| **ADFS (on-premises)** | SAML 2.0 | P0 | Government ministries, air-gapped |
| **Okta** | OIDC / OAuth 2.0 | P1 | International enterprise |
| **Google Workspace** | OIDC | P2 | SME / startup clients |
| **Local LDAP/AD** | LDAP | P0 | On-premises government |

### 1.2 Authentication Flow

```
User → AWI Login Page
     → Redirect to IdP (Entra ID / ADFS / LDAP)
     → IdP authenticates user
     → Returns SAML assertion or JWT
     → AWI validates token signature
     → Resolves tenant_id from claim (e.g. org domain)
     → Issues short-lived AWI session token (4-hour TTL)
     → Logs authentication event to tenant_audit_log
```

### 1.3 Token Claims Required

AWI requires the following claims from the identity provider:

```json
{
  "sub": "user-id",                     // unique user identifier
  "email": "user@organisation.com",     // used for audit trail
  "groups": ["AWI_CHRO", "AWI_Analyst"], // RBAC group membership
  "tenant": "snb-sa-prod",             // AWI tenant_id mapping
  "preferred_username": "fname.lname"  // display name
}
```

### 1.4 Microsoft Entra ID Configuration

```yaml
App Registration (AWI):
  Type: Enterprise Application
  Sign-in URL: https://awi.organisation.com/auth/sso
  Identifier (Entity ID): https://awi.organisation.com
  Reply URL: https://awi.organisation.com/auth/callback

Group Claim Mapping:
  AWI_CHRO       → AWI CHRO Role (full access)
  AWI_Manager    → HR Manager Role (team-level)
  AWI_Analyst    → HR Analyst Role (read + export)
  AWI_ReadOnly   → Read-Only Role (dashboard view)

Conditional Access:
  Require MFA: Yes (for CHRO and Admin roles)
  Session lifetime: 4 hours
  IP restriction: Corporate network or VPN required
```

---

## 2. Role-Based Access Control (RBAC)

### 2.1 AWI Roles

| Role | Code | Who | Permissions |
|---|---|---|---|
| **CHRO** | `awi_chro` | Chief HR Officer | Full access: all analysis, all exports, user management, audit log |
| **HR Manager** | `awi_manager` | HR Director, HR Business Partner | Analysis, exports (PDF/CSV), strategy simulator, no user management |
| **HR Analyst** | `awi_analyst` | HR Data Analyst, People Analytics | Analysis, read-only exports (CSV), no PDF board reports, no simulator |
| **Executive Viewer** | `awi_exec` | CEO, CFO, Board Member | Dashboard view only, CEO Brief, no data access, no exports |
| **Governance Auditor** | `awi_auditor` | Legal, Compliance, Internal Audit | Governance panel + audit log read-only, no analysis or exports |
| **Platform Admin** | `awi_admin` | IT Admin, HR Systems Manager | Tenant management, user provisioning, no employee data access |

### 2.2 Permission Matrix

| Capability | CHRO | Manager | Analyst | Exec Viewer | Auditor | Admin |
|---|---|---|---|---|---|---|
| Upload & analyze data | ✓ | ✓ | ✓ | — | — | — |
| View workforce dashboard | ✓ | ✓ | ✓ | ✓ | — | — |
| View individual risk table | ✓ | ✓ | ✓ | — | — | — |
| Export PDF board report | ✓ | ✓ | — | — | — | — |
| Export McKinsey deck | ✓ | ✓ | — | — | — | — |
| Export CSV data | ✓ | ✓ | ✓ | — | — | — |
| Run strategy simulator | ✓ | ✓ | — | — | — | — |
| View governance panel | ✓ | ✓ | ✓ | — | ✓ | — |
| View audit log | ✓ | — | — | — | ✓ | ✓ |
| Manage users | ✓ | — | — | — | — | ✓ |
| Manage tenant settings | ✓ | — | — | — | — | ✓ |

### 2.3 RBAC Implementation Plan

```python
# Phase 31 target API — not yet implemented
from backend.core.rbac import RBACEngine, AWIRole, AWIPermission

rbac = RBACEngine()

@app.post("/api/local/export/board-report")
async def export_board_report(
    request: Request,
    user: AWIUser = Depends(get_current_user),
):
    rbac.require_permission(user, AWIPermission.EXPORT_PDF_REPORT)
    # ... export logic
```

---

## 3. Executive Roles — Board-Level Access

The `awi_exec` (Executive Viewer) role is designed specifically for C-suite board access:

**What executives see:**
- CEO Intelligence Brief (30-second summary)
- Workforce Risk Index (aggregate, no individual names)
- Executive Priority Score
- Strategic recommendations (board language)
- Bilingual EN/AR toggle

**What executives never see:**
- Individual employee names, IDs, or risk scores
- Raw data tables
- ML technical metrics
- Export controls

**Implementation:** CEO Dashboard page already architecturally separates aggregate intelligence from individual-level data. The `awi_exec` role will be enforced at the navigation level — `awi_exec` users see only `ceo` and `decision` pages.

---

## 4. Audit Logging Architecture

Every user action that touches employee data or generates an export is logged to an immutable audit trail.

### 4.1 Audit Events

| Event Type | Trigger | Logged Data |
|---|---|---|
| `user_authenticated` | SSO login | user_id, role, tenant_id, IP (masked) |
| `analysis_run` | File upload + analysis | tenant_id, session_id, row_count, timestamp |
| `export_generated` | PDF/CSV/PPTX export | export_type, tenant_id, user_id, timestamp |
| `individual_risk_viewed` | Risk table opened | tenant_id, user_role, row_count_visible |
| `governance_panel_accessed` | Governance page opened | tenant_id, user_role |
| `session_ended` | Logout or timeout | session_duration, actions_count |
| `tenant_admin_action` | User created/deactivated | admin_user_id, action, affected_user |

### 4.2 Audit Log Properties

- **Immutable**: Rows are INSERT-only. No UPDATE or DELETE permitted on audit_log table.
- **Tenant-scoped**: Each tenant's audit log is isolated (accessed only via their tenant_id)
- **No PII**: Employee names/IDs never appear in audit events — only counts and timestamps
- **Exportable**: Governance Auditor role can export audit log as CSV for PDPL compliance reporting
- **Retention**: Configurable per tenant (default: 24 months per PDPL Article 29)

### 4.3 PDPL Article 31 Compliance

Saudi PDPL Article 31 requires organisations to maintain records of personal data processing activities. AWI's audit log satisfies this requirement by recording:
- When analysis was run (timestamp)
- How many records were processed (row_count — not the records themselves)
- Who triggered the analysis (user_id, masked)
- What outputs were generated (export type)
- Whether governance checks passed (governance_passed flag)

---

## 5. Air-Gapped Government Deployment

For Saudi government ministries that cannot connect to any external identity provider:

### 5.1 Local Identity Mode

AWI will support a **local identity store** for air-gapped environments:
- Users stored in SQLite (hashed credentials, bcrypt)
- No external IdP dependency
- MFA via TOTP (Google Authenticator compatible)
- Admin user created during on-premises installation

### 5.2 Configuration

```yaml
# awi_config.yaml
auth:
  mode: local                     # local | entra | adfs | okta
  session_ttl_hours: 8
  require_mfa: true
  mfa_method: totp

local_identity:
  admin_email: admin@ministry.gov.sa
  password_policy:
    min_length: 12
    require_uppercase: true
    require_numbers: true
    max_age_days: 90
```

---

## 6. Implementation Phases

| Phase | Deliverable | Target |
|---|---|---|
| **Phase 30** (complete) | Tenant foundation, session tracking | Done |
| **Phase 31A** | Local identity store + session tokens | Q3 2026 |
| **Phase 31B** | RBAC enforcement across all API endpoints | Q3 2026 |
| **Phase 31C** | Microsoft Entra ID / SAML 2.0 SSO integration | Q4 2026 |
| **Phase 31D** | Executive Viewer role + board access controls | Q4 2026 |
| **Phase 31E** | Audit export + PDPL Article 31 report | Q4 2026 |
| **Phase 32** | ADFS (on-premises) + local LDAP for government | Q1 2027 |

---

## 7. Security Standards

All authentication implementation will conform to:

| Standard | Requirement |
|---|---|
| OWASP ASVS Level 2 | Session management, input validation, access control |
| NIST SP 800-63B | Password strength, MFA, session binding |
| Saudi PDPL Article 6 | Automated processing notification |
| Saudi PDPL Article 29 | Data processing records retention |
| ISO 27001 | Access control policy alignment |

---

*AWI Enterprise Authentication Roadmap — Phase 30D | 2026-06-01*
