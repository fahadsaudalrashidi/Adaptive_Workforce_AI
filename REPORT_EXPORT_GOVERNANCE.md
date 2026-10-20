# Report Export Governance — Phase 9

**Document Type:** Governance Architecture Reference  
**Phase:** 9  
**Date:** 2026-05-21  
**Audience:** CIO, Compliance, Legal, External Auditors

---

## Overview

The Report Export Governance framework defines the controls applied to every report and export package produced by the Adaptive Workforce Intelligence platform. These controls cannot be disabled or bypassed through configuration.

---

## Mandatory Disclaimer Attachment

Every report, regardless of type or language, must carry three governance notices:

| # | Notice | Purpose |
|---|--------|---------|
| 1 | **Governance Disclaimer** | Requires HR professional review before any workforce decision |
| 2 | **Confidence Warning** | States that predictions are probabilistic, not deterministic |
| 3 | **PDPL Review Note** | States that legal compliance requires qualified Saudi legal counsel |

**Enforcement:** `ReportLocalizer.all_disclaimers()` returns all three in the configured language. `ExecutiveReportExporter` attaches them to every report. The `ExportSafetyValidator` (Phase 7) provides a secondary check before any external export.

**Audit:** Each exported report records `disclaimers_attached: int` (must equal 3).

---

## Four Report Types

| Report Type | Audience | Key Content | No Employee Data |
|-------------|---------|-------------|-----------------|
| `executive_summary` | CHRO / CEO | WSI, department risk table, strategic insights | ✓ |
| `governance_audit` | CIO / Compliance | Governance lock status, PDPL controls table | ✓ |
| `board_briefing` | Board / Board member | WSI trend, theory contributions, insights | ✓ |
| `data_readiness` | IT / Data team | Scan readiness, data quality KPIs, recommendations | ✓ |

All four types include:
- GovernanceStatus bar (emerald = OK, amber = WARNING)
- Mandatory disclaimers section (cannot be moved to an appendix)
- Report ID, tenant ID, generated_at timestamp
- SHA-256 checksum of HTML content for tamper detection

---

## HTML + PDF Output

- **HTML** is always produced. It is the primary output format.
- **PDF** is a best-effort secondary output via fpdf2. If fpdf2 is unavailable, PDF is `None` and HTML is used.
- PDFs carry the same governance notices as the HTML version.
- PDF generation failure does not block HTML delivery.

---

## No Individual Employee Data

**Hard constraint:** No report type includes:
- Employee names
- Employee IDs or national IDs
- Individual probability scores (y_prob, risk_score at individual level)
- Any field that could re-identify a specific employee

This is enforced by:
1. `ExportSafetyValidator._is_employee_level_field()` — exact set membership check
2. `EMPLOYEE_LEVEL_OUTPUT_ENABLED = False` governance lock
3. Report data templates that operate only on department-level aggregates

---

## Audit Package Export

**Module:** `backend/core/audit_package_builder.py`  
**Output:** ZIP archive containing:

```
audit_package_{tenant_id}.zip
├── scan_summary.json          — Governance scan result (no raw rows)
├── ingestion_metadata.json    — Column types, row counts, transformations
├── report_manifest.json       — Generated reports with SHA-256 checksums
├── governance_snapshot.json   — Production lock values at export time
├── audit_events_excerpt.json  — PII-safe audit event log
├── README.txt                 — Human-readable package description
└── MANIFEST.json              — File manifest with per-file checksums
```

**Manifest checksum:** The MANIFEST.json is itself SHA-256 hashed, providing a package-level integrity seal.

**PII sanitization in audit events:** Event fields `employee_id`, `full_name`, `email`, `national_id`, `iqama` are stripped before inclusion. National ID and Iqama patterns in `summary` fields are redacted to `[REDACTED]`.

---

## Bilingual Report Governance

Reports are generated in English (`en`) or Arabic (`ar`). The governance notices are authored in both languages — not machine-translated. Arabic reports use RTL layout metadata for correct PDF rendering.

The `PDPL_NOTE` in Arabic explicitly states the same legal limitations as the English version:
> لا تُصادق هذه المنصة على الامتثال القانوني. ("This platform does not certify legal compliance.")

This language cannot be softened or removed in any localized version.

---

## Checksum Verification

Each `ExportedReport` carries:
```python
checksum: str  # SHA-256 of html_content (64 hex chars)
```

Recipients can verify report integrity by hashing the received HTML content with SHA-256 and comparing to the reported checksum.

---

## Governance Lock Snapshot

Every audit package includes the values of all production governance locks at the time of package creation. This creates an auditable record that the platform was correctly configured at the moment of each export.

Expected values in any valid audit package:

| Lock | Expected Value |
|------|---------------|
| DEBUG | False |
| EMPLOYEE_LEVEL_OUTPUT_ENABLED | False |
| SCIENTIFIC_FEATURE_MODE | "theory_grounded" |
| LEGACY_CONSTRUCTS_DISABLED | True |
| PDPL_WARNING_ENABLED | True |
| REPORT_DISCLAIMER_REQUIRED | True |
| AUDIT_LOGGING_REQUIRED | True |
| TEMPORAL_VALIDATION_REQUIRED | True |
| SECURE_EXPORT_MODE | True |
| TENANT_ISOLATION_REQUIRED | True |
| CALIBRATION_AUDIT_REQUIRED | True |

A deviating value in any audit package indicates a misconfigured or non-production deployment.
