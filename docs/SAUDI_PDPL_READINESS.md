# Saudi PDPL Readiness Assessment
**Phase:** 6 — Enterprise Commercialization & Deployment Architecture
**Status:** PARTIAL READINESS (Technical controls in place; legal review required)
**Date:** 2026-05-20

---

## IMPORTANT DISCLAIMER

This document describes the TECHNICAL controls implemented in the Adaptive Workforce AI platform that are relevant to PDPL compliance. It does NOT constitute legal advice. It does NOT certify compliance with PDPL or any other regulation. Before deploying this system with real employee data, formal legal review by qualified Saudi legal counsel is mandatory.

---

## 1. PDPL Overview

The Saudi Personal Data Protection Law (PDPL), issued by Royal Decree No. M/19 dated 9 Safar 1443H (September 16, 2021), and the implementing regulations (PDPL Regulations, issued by SDAIA), govern the processing of personal data of Saudi residents. Key provisions relevant to HR analytics:

| PDPL Article | Requirement | Relevance |
|---|---|---|
| Art. 4 | Lawful basis for processing | HR analytics requires a lawful basis (employee consent or legitimate interest) |
| Art. 5 | Purpose limitation | Data collected for HR may only be used for HR purposes |
| Art. 9 | Sensitive data | Health, financial, and behavioral data subject to higher standards |
| Art. 14 | Data subject rights | Employees have right to access, correct, and object to processing |
| Art. 25 | Automated decisions | Automated profiling that significantly affects individuals requires specific conditions |
| Art. 27–29 | Cross-border transfer | Personal data transfer outside Saudi Arabia requires SDAIA approval |
| Art. 32 | Security requirements | Appropriate technical and organizational measures required |

---

## 2. Technical Controls Implemented

### 2.1 PII Detection (Technical Control — ACTIVE)

The platform detects personally identifiable information before it reaches the ML pipeline:

| PII Type | Detected By | Action |
|---|---|---|
| National ID (رقم الهوية) | `SaudiSchemaIntelligenceEngine` + `SaudiDataGovernanceEngine` | BLOCK onboarding |
| Iqama number (رقم الإقامة) | Both engines | BLOCK onboarding |
| IBAN / bank account | Both engines | BLOCK onboarding |
| Phone number | Both engines | BLOCK onboarding |
| Personal email | Both engines | BLOCK onboarding |
| Passport number | Both engines | BLOCK onboarding |
| Home address / GPS | Both engines | BLOCK onboarding |
| GOSI number | Both engines | BLOCK onboarding |

**Limitation:** Pattern matching detects known PII column names. PII embedded in free-text fields (e.g., comments column containing "Employee's ID is 1234567890") is not detected. Free-text columns must be reviewed manually before onboarding.

### 2.2 Individual Profiling Protection (Technical Control — ACTIVE)

PDPL Art. 25 restricts "automated individual decisions that significantly affect" data subjects. The platform implements the following technical controls:

1. **Executive reports contain no individual scores** — `ExecutiveReportingLayer` produces department-level aggregates only
2. **Language guard blocks deterministic individual predictions** — no "Employee X will leave" text in any report
3. **No individual HR decisions are automated** — the system produces probabilistic risk indicators, not directives
4. **HR professional review required** — governance notes in all reports specify human-in-the-loop requirement

**Architecture note:** Individual-level risk scores (`y_prob` values) exist internally in the pipeline but are not returned to end users through the executive reporting layer. Access to individual scores requires `hr_admin` role, a separate API endpoint with additional audit logging, and is subject to export controls (see DEPLOYMENT_ARCHITECTURE.md §4.2).

### 2.3 Data Minimization (Technical Control — PARTIAL)

The platform implements data minimization through the `ModelInputContract`:
- Only features that pass governance checks enter the model
- PII columns are blocked from model training
- Leakage columns are blocked from model training
- Legacy/unsupported constructs are blocked

**Gap:** Data minimization at the upload stage (before onboarding) must be implemented in the API gateway layer. The current Python code receives a full DataFrame — it does not control what columns the client uploads.

### 2.4 Purpose Limitation (Technical Control — PARTIAL)

The platform is designed exclusively for HR attrition risk analysis. No functionality exists for:
- Marketing profiling
- Credit scoring
- Insurance underwriting
- Law enforcement

**Gap:** Purpose limitation is enforced by code scope, not by a technical control that prevents misuse. A client who uploads non-HR data (e.g., customer data) would need to be blocked at the API layer, not by the ML pipeline.

### 2.5 Audit Trail (Technical Control — ACTIVE)

All processing stages are logged:
- `OnboardingReport` records what was checked and what was found
- `OnboardingReport.assessed_at` provides timestamped evidence of processing
- Governance notes provide a human-readable trail of data quality decisions

**Gap:** The audit trail exists in Python dataclass form. A production deployment must serialize these reports to an immutable, append-only audit log store (see DEPLOYMENT_ARCHITECTURE.md §5.2).

### 2.6 Data Subject Rights (Technical Control — NOT IMPLEMENTED)

PDPL Art. 14 grants employees the right to:
- Know what data is processed about them
- Access their data
- Correct inaccurate data
- Object to processing

**Gap:** No technical controls exist for data subject rights fulfillment. This must be implemented as a separate workflow, typically through the HR system of record (not the analytics platform). The platform does not store employee data permanently — it processes datasets on demand.

---

## 3. Legal Requirements (Not Yet Fulfilled)

### 3.1 Data Processing Agreement (MANDATORY)

Before processing any real employee data, a Data Processing Agreement (DPA) must be executed between:
- The data controller (the client organization)
- The data processor (the platform operator)

The DPA must specify:
- What data is processed
- For what purpose
- For how long
- Where it is stored
- Sub-processor arrangements
- Security measures
- Data subject rights procedures

**Status:** Template DPA not yet drafted. Legal counsel engagement required.

### 3.2 Employee Notice (MANDATORY)

PDPL Art. 11–13 requires that data subjects (employees) be informed of automated processing. The notice must be provided:
- Before processing begins
- In Arabic (PDPL Art. 4 requires disclosure in Arabic for Saudi residents)
- In plain language

The notice must include:
- What data is used
- How it is used (risk scoring for workforce planning)
- Who receives the output (HR leadership)
- Data retention period
- How to exercise data subject rights

**Status:** Employee notice template not yet drafted.

### 3.3 Data Residency (MANDATORY)

Unless SDAIA approval for cross-border transfer is obtained, all processing and storage must occur within Saudi Arabia.

**Technical readiness:** The Python pipeline is location-agnostic. Deployment in Saudi region is a cloud infrastructure decision.

**Status:** Cloud region not yet selected. AWS me-south-1 (Riyadh) or local data center required.

### 3.4 SDAIA Registration (VERIFY REQUIREMENT)

Saudi Data Governance Authority (SDAIA) may require registration of data controllers and processors handling personal data of Saudi residents at scale. Legal counsel should verify whether this platform qualifies for registration requirements under current PDPL implementing regulations.

**Status:** Not assessed. Legal counsel required.

---

## 4. Export Control Governance

### 4.1 Individual Risk Score Export

Individual-level risk scores are the highest-sensitivity output. Export controls (to be implemented at the API/infrastructure layer):

- Export of individual scores requires `hr_admin` role + two-factor approval workflow
- Each export is watermarked with the requesting user's ID
- Exported files must not contain National ID, Iqama, or other PDPL-sensitive fields
- Export is logged in the immutable audit trail

### 4.2 Aggregate Report Export

Executive reports (department-level aggregates) have lower sensitivity:
- Export requires `hr_admin` or `executive` role
- Reports may be shared internally with HR leadership
- External sharing (to consultants, auditors) requires HR Director approval

### 4.3 Prohibited Exports

The following must never be exported:
- Raw uploaded HR dataset (once processed, the raw file should be deleted)
- Individual-level scores sent to email or messaging platforms
- Any report containing National ID or Iqama numbers (PII detection should have blocked these, but verify)
- Model weights or feature importance rankings that could be reverse-engineered to infer individual risk

---

## 5. Pre-Deployment Compliance Checklist

Before the first real client deployment:

**Legal:**
- [ ] Data Processing Agreement drafted and reviewed by qualified Saudi legal counsel
- [ ] Employee notice template drafted in Arabic and English
- [ ] Cross-border transfer policy documented
- [ ] SDAIA registration requirement assessed
- [ ] Automated profiling disclosure documented under PDPL Art. 25

**Technical:**
- [ ] Saudi cloud region selected for data residency
- [ ] Audit log store implemented (immutable, append-only)
- [ ] Data subject rights workflow implemented in HR system
- [ ] API gateway PII scanning implemented (pre-Python layer)
- [ ] Free-text column review process documented
- [ ] Export control workflow implemented

**Process:**
- [ ] HR professional sign-off process for each new deployment
- [ ] Model retraining governance policy documented
- [ ] Data retention policy documented (how long are uploaded datasets kept?)
- [ ] Incident response plan for data breach

---

## 6. What This Document Cannot Provide

1. **Legal certification of PDPL compliance** — only qualified Saudi legal counsel can assess compliance
2. **SDAIA approval** — regulatory approval is granted by SDAIA, not by the developer
3. **Formal Data Protection Impact Assessment (DPIA)** — a DPIA requires involvement of qualified privacy professionals
4. **Binding legal advice** — this document is a technical assessment only

---

*PDPL readiness assessment produced as part of Phase 6 — Enterprise Commercialization & Deployment Architecture. This document does not constitute legal advice. Formal legal review by qualified Saudi counsel is mandatory before deployment with real employee data.*
