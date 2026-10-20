# Enterprise Upload Workflow — Phase 9

**Document Type:** Technical Workflow Reference  
**Phase:** 9 — Enterprise Data Upload, Executive Report Export & Product Completion  
**Date:** 2026-05-21  
**Audience:** IT Integrators, HR Administrators, Compliance Teams

---

## Overview

The Enterprise Upload Workflow is the end-to-end pathway by which a tenant's HR dataset travels from raw file bytes to a governance-validated, theory-activated analysis state. The workflow enforces all Phase 1–8 governance constraints before any analytics are performed.

---

## Workflow Stages

```
[File Bytes] → Stage 1: File Parsing → Stage 2: Governance Scan → Stage 3: Theory Activation → [Analysis Ready]
```

### Stage 1 — File Parsing (ExcelIngestionEngine)

**Module:** `backend/core/excel_ingestion_engine.py`  
**Entry point:** `ExcelIngestionEngine.ingest(raw_bytes, filename) → IngestionResult`

| Supported Format | Parser |
|-----------------|--------|
| .xlsx / .xls | openpyxl (`data_only=True` — formulas stripped) |
| .csv | pandas (multi-encoding: utf-8-sig → utf-8 → cp1256 → windows-1256 → latin-1) |
| .parquet | pandas + pyarrow |
| .json | pandas (record-oriented) |

**Transformations applied:**
- Hidden Excel rows: included with warning
- Multi-sheet Excel: best HR-relevant sheet selected by keyword scoring
- Duplicate column names: renamed with `_N` suffix
- Salary columns: currency symbols and commas stripped
- Arabic booleans (نعم/لا): normalized to True/False

**IngestionResult fields (no raw row data returned to API):**
- `success`, `row_count`, `column_count`
- `original_headers`, `normalized_headers`
- `detected_language` — `'en'` | `'ar'` | `'mixed'`
- `detected_erp_style` — Workday / SAP SuccessFactors / Oracle HCM / Mudad / Qiwa / BambooHR
- `encoding_used`, `sheet_used`
- `warnings`, `transformations`

---

### Stage 2 — Governance Scan (SecureFileIngestion)

**Module:** `backend/core/secure_file_ingestion.py`  
**Entry point:** `SecureFileIngestion.scan(raw_bytes, filename, tenant_id) → FileIngestionReport`

**Checks performed (in order):**

| Check | Blocking? | Notes |
|-------|-----------|-------|
| Tenant ID validation | BLOCKED | Must be non-empty string |
| File parsing | BLOCKED if fails | Delegates to ExcelIngestionEngine |
| PII column detection | BLOCKED | Exact + regex pattern matching |
| Leakage column detection | BLOCKED | Post-event columns: resignation_date, terminated, etc. |
| Minimum row count | BLOCKED | < 50 rows → BLOCKED |
| Feature column count | BLOCKED | < 3 HR-relevant columns → BLOCKED |
| Duplicate rows | Warning only | Logged in warnings list |
| Missing value rate | Warning if > 30% | |
| Empty columns | Warning only | |
| High-null columns (>50%) | Warning only | |
| Salary distribution anomaly | Warning only | |

**ReadinessLevel:**
- `READY` — No blocking issues, no warnings
- `CONDITIONAL` — No blocking issues, warnings present (user should review before proceeding)
- `BLOCKED` — One or more blocking issues; file cannot proceed to analysis

**STOP condition (enforced):** If `readiness_level == BLOCKED`, the UI must not allow progression to theory activation.

---

### Stage 3 — Theory Activation

Theory activation (via `TheoryAwareFeatureEngine`) begins only after `ReadinessLevel.READY` or `ReadinessLevel.CONDITIONAL` (with user confirmation). The existing Phase 5–7 constructs (COR, JD-R, FFM, Mobley, Adams Equity) are applied without modification.

---

## API Endpoints

### File Upload & Scan

```
POST /v1/tenants/{tenant_id}/upload/scan
Content-Type: multipart/form-data
Body: file=<binary>

Response:
{
  "tenant_id": "acme-corp",
  "readiness_level": "READY" | "CONDITIONAL" | "BLOCKED",
  "governance_scan_passed": true | false,
  "pii_columns_detected": [],
  "leakage_columns_detected": [],
  "feature_columns": [...],
  "blocking_reasons": [],
  "warnings": [],
  "data_quality": { "total_rows": 3247, "duplicate_rows": 0, ... },
  "ingestion": { "row_count": 3247, "detected_language": "en", ... }
}
```

**Note:** Raw DataFrame rows are never returned in the API response. Only metadata is serialized.

### Demo Company Scan

```
GET /v1/tenants/{tenant_id}/upload/demo/{company_id}
GET /v1/tenants/{tenant_id}/upload/demo-profiles
```

---

## Governance Invariants

1. **Tenant isolation** — Every scan is scoped to a single tenant_id. Cross-tenant file access raises PermissionError.
2. **PII blocking** — Files with national_id, email, name, iqama, IBAN, phone, or date_of_birth columns are BLOCKED, not warned.
3. **Leakage blocking** — Files with resignation_date, termination_date, or similar post-event columns are BLOCKED.
4. **No raw rows in API** — The `df` attribute of `IngestionResult` is internal; it is never serialized into API responses.
5. **Empty file protection** — Zero-byte files return `success=False` from the ingestion engine.

---

## Error Handling

All failure cases return a structured response (not an HTTP 4xx error), with `readiness_level=BLOCKED` and a human-readable `blocking_reasons` list. The UI uses this to display actionable guidance to the HR user.

Exception: missing tenant_id returns HTTP 400 from the API layer before reaching the engine.
