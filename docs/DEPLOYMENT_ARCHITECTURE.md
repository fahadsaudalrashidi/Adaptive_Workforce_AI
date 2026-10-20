# Deployment Architecture
**Phase:** 6 — Enterprise Commercialization & Deployment Architecture
**Status:** DESIGN COMPLETE
**Date:** 2026-05-20

---

## 1. Architecture Overview

The Adaptive Workforce AI platform is designed as a stateless, tenant-isolated workforce intelligence service. Every request carries its own data; no cross-request state is shared. This design makes multi-tenant isolation architectural rather than configuration-dependent.

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                                │
│  HR Dashboard  │  Executive Reports  │  API Clients  │  Export  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / OAuth 2.0
┌──────────────────────────▼──────────────────────────────────────┐
│                     API GATEWAY                                  │
│  Rate limiting  │  Auth (JWT)  │  Tenant routing  │  Audit log  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   ONBOARDING PIPELINE                            │
│  Schema fingerprint → Governance validation → Leakage scan      │
│  Theory compatibility → Construct rejection → Readiness score   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Approved dataset only
┌──────────────────────────▼──────────────────────────────────────┐
│                   SCIENCE PIPELINE                               │
│  TheoryAwareColumnMapper → compute_constructs                    │
│  ModelInputContract → TemporalValidationGuard → feature_factory  │
│  Model training / inference → Calibration audit                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│               REPORTING & GOVERNANCE LAYER                       │
│  ExecutiveReportingLayer → EnterpriseLanguageGuard               │
│  ROIEstimationEngine → CalibrationReliabilityAuditor             │
│  Audit log append → Report store                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-Tenant Isolation

### 2.1 Isolation Model

**Tenant isolation is stateless by design.** No module in the pipeline maintains class-level or module-level mutable state that persists across requests. Each call to:

- `EnterpriseOnboardingPipeline.run()` — stateless, returns a new `OnboardingReport`
- `ROIEstimationEngine.estimate()` — stateless
- `ExecutiveReportingLayer.generate()` — stateless (instantiates new `EnterpriseLanguageGuard`)
- `SaudiSchemaIntelligenceEngine.analyse()` — stateless
- `SaudiDataGovernanceEngine.validate()` — stateless

receives its own input, produces its own output, and shares nothing with other calls.

### 2.2 Tenant Identifier Scope

`company_id` is used for:
- Audit log tagging
- Report metadata (`OnboardingReport.company_id`)
- Storage path routing (to be implemented in infrastructure layer)

`company_id` is NEVER used for:
- Data filtering (no "show me only this tenant's data" logic in ML code)
- Model selection (one model per tenant, deployed separately)
- Feature gating

### 2.3 Database-Level Isolation (Infrastructure)

At the storage layer (outside this Python codebase):
- Each tenant's data resides in a separate database schema or storage container
- Cross-tenant queries are architecturally prevented by IAM policy, not application code
- Audit logs are append-only per tenant

### 2.4 Model Isolation

Each tenant trains their own model on their own data. Model artifacts are stored per-tenant:
```
models/
  {company_id}/
    model_{version}.pkl
    calibration_report_{version}.json
    onboarding_report_{version}.json
    feature_manifest_{version}.json
```

No cross-tenant model sharing. No transfer learning across tenants (would require explicit governance review).

---

## 3. Environments

### 3.1 Environment Tiers

| Environment | Purpose | Data | Access |
|---|---|---|---|
| Development | Feature development | Synthetic / anonymized IBM | Engineers |
| Staging | Integration testing | Anonymized client samples | QA + Engineers |
| Production | Live tenant serving | Real client HR data | Ops + HR admins |
| DR (Disaster Recovery) | Failover | Mirrors production | Ops only |

### 3.2 Staging vs Production Separation

Critical differences between staging and production:

1. **Data:** Staging uses anonymized data only. PII and real salary data never enter staging.
2. **Credentials:** Staging and production use separate credential stores. Staging credentials cannot access production storage.
3. **Model artifacts:** Models trained in staging are not automatically promoted to production — a manual review gate is required.
4. **Audit logging:** Both environments produce audit logs, but staging logs are not legally significant and are retained for 30 days only (vs. 7 years for production).

### 3.3 Promotion Gate (Staging → Production)

Before any model is deployed to production:
- [ ] `CalibrationReliabilityReport.overall_reliability != "CRITICAL"`
- [ ] Full 352-test suite passes
- [ ] `OnboardingReport.overall_status` for client dataset is `READY` or `CONDITIONAL`
- [ ] Language guard audit passes on all report templates
- [ ] PDPL checklist reviewed (see `SAUDI_PDPL_READINESS.md`)
- [ ] HR professional sign-off on sample report output

---

## 4. Role-Based Access Control

### 4.1 Roles

| Role | Capabilities |
|---|---|
| `hr_admin` | Upload datasets, view department summaries, trigger onboarding |
| `hr_analyst` | View reports, run what-if scenarios (no data upload) |
| `executive` | View executive reports only — no raw data access |
| `data_scientist` | Full pipeline access — no production data in development environment |
| `system_admin` | Infrastructure access — no HR data access |
| `auditor` | Read-only access to audit logs and governance reports |

### 4.2 HR-Only Restricted Actions

The following actions require the `hr_admin` role AND a second-factor confirmation:
- Dataset upload (triggers onboarding pipeline)
- Model retraining
- Export of individual-level risk scores (requires approval workflow)
- Deletion of tenant data (requires dual authorization)

Individual-level risk scores (not aggregate reports) are restricted to `hr_admin` only, are watermarked with the requesting user's ID, and are logged in the audit trail.

### 4.3 Executive Access Boundary

Users with the `executive` role receive only:
- `ExecutiveReport` output (department aggregates)
- `BusinessValueReport` output (cost estimates with ranges)
- No access to raw feature data
- No access to individual employee risk scores
- No access to model weights or feature importance rankings

---

## 5. API Design

### 5.1 Endpoints

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/v1/onboarding/upload` | POST | hr_admin | Upload dataset, trigger onboarding pipeline |
| `/v1/onboarding/report/{job_id}` | GET | hr_admin, hr_analyst | Retrieve onboarding report |
| `/v1/model/train` | POST | hr_admin | Trigger model training on approved dataset |
| `/v1/model/predict` | POST | hr_admin, hr_analyst | Run predictions on new data |
| `/v1/reports/executive` | GET | executive, hr_admin | Retrieve executive report |
| `/v1/reports/roi` | GET | hr_admin | Retrieve ROI estimate report |
| `/v1/governance/audit-log` | GET | auditor, hr_admin | Retrieve audit log entries |
| `/v1/governance/calibration` | GET | hr_admin, data_scientist | Retrieve calibration report |

### 5.2 Audit Logging

Every API call logs:
- Timestamp (UTC)
- `company_id` (tenant)
- User ID (from JWT)
- Endpoint
- Input data hash (not raw data)
- Output data hash
- Governance flags raised (if any)
- Response status

Audit logs are immutable, append-only, and retained for 7 years in production.

---

## 6. Future Cloud Deployment

### 6.1 Target Architecture

Designed for deployment on a cloud platform (Azure, AWS, or on-premise Saudi data center depending on PDPL requirements):

```
Load Balancer
    ↓
API Gateway (Auth + Rate Limit)
    ↓
Application Service (Containerized Python, autoscaling)
    ↓
Object Storage (Dataset + Model artifacts, per-tenant buckets)
    ↓
Database (Audit log, tenant registry, report metadata)
```

### 6.2 Saudi Data Residency

PDPL requires that personal data of Saudi residents be processed and stored within Saudi Arabia unless specific cross-border transfer conditions are met (PDPL Art. 27–29). This means:

- **Primary compute and storage must be in a Saudi data center** (or a region with Saudi PDPL bilateral agreement)
- As of 2026, AWS Riyadh Region (me-south-1) and Microsoft Azure UAE North satisfy this requirement — confirm with legal counsel before deployment
- Model weights themselves do not contain personal data and may be stored globally, but the data used to train them must be processed in-region

### 6.3 Scalability

The stateless pipeline design enables horizontal scaling: multiple instances can handle concurrent tenant requests without coordination. The only shared state is the model artifact store (read-only during inference), which scales independently.

---

## 7. Governance Integration Points

The architecture enforces governance at three independent layers:

1. **Onboarding gate** — PII/leakage blocks data before it reaches the science pipeline
2. **Model Input Contract** — blocks non-theory features from reaching model training
3. **Language guard** — blocks non-compliant language from reaching report output

A bypass of any one layer would be caught by the others. All three must be simultaneously disabled to circumvent governance — which requires code changes that would be detected in the audit trail.

---

*Architecture produced as part of Phase 6 — Enterprise Commercialization & Deployment Architecture. Scientific traceability governed by the research paper PDF as primary source of truth.*
