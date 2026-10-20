# Enterprise Upload Workflow Audit — Phase 11

**Date:** 2026-05-21  
**Components:** `DataUpload.tsx`, `SecureFileIngestion`, `ExcelIngestionEngine`, `DatasetTypeClassifier`

---

## 1. Upload Workflow Overview

The enterprise upload flow is a 3-state UI with 5 backend validation stages:

```
UI States:        select → scanning → results
Backend stages:   ingest → PII scan → leakage scan → type classify → readiness verdict
```

## 2. UI States

### State 1: Select
Two modes available:
- **Demo Companies** (default): 5 synthetic Saudi enterprise datasets, no file required
- **Upload File**: Drag-and-drop or click to upload (.xlsx, .xls, .csv, .parquet, .json)

PII warning displayed prominently in upload mode.

### State 2: Scanning
- Animated loading indicator (no freeze)
- Descriptive scanning message in EN/AR
- Background: PII detection, leakage scan, quality assessment, type classification

### State 3: Results
- Readiness banner: READY / CONDITIONAL / BLOCKED with color coding
- Data quality KPIs: rows, columns, feature columns, language
- ERP detection display (if relevant)
- PII columns list (if detected)
- Leakage columns list (if detected)
- Blocking reasons (if BLOCKED)
- Warnings (if CONDITIONAL)
- All-clear confirmation (if READY)

## 3. Governance Validation Stages

| Stage | Module | What is checked |
|-------|--------|----------------|
| 1. File ingestion | `ExcelIngestionEngine` | Format, encoding, multi-sheet, Arabic headers |
| 2. PII detection | `SecureFileIngestion` | national_id, email, phone, iqama, passport |
| 3. Leakage scan | `SecureFileIngestion` | resignation_date, termination_date, terminated, left |
| 4. Quality check | `SecureFileIngestion` | Row minimum (50), feature column minimum (3) |
| 5. Type classification | `DatasetTypeClassifier` | EMPLOYEE_ATTRITION vs JOB_MARKET vs UNKNOWN |

## 4. Analysis Routing by Dataset Type

| Dataset Type | Dashboard Mode | Attrition Allowed | Report Type |
|-------------|---------------|-------------------|-------------|
| `EMPLOYEE_ATTRITION_DATASET` | `workforce_stability` | YES | Executive Summary, Governance, Board Briefing |
| `JOB_MARKET_POSTING_DATASET` | `market_intelligence` | NO | Market Intelligence Summary |
| `GLOBAL_JOB_POSTING_STRESS_TEST` | `ingestion_stress_test` | NO | Data Readiness only |
| `UNKNOWN_OR_UNSUPPORTED` | `blocked` | NO | Upload blocked — no report |

## 5. Error Handling Principles

The upload UI follows enterprise UX principles:
- **Never freeze**: all async operations have loading states
- **Never expose stack traces**: Python exceptions are caught and mapped to user-friendly messages
- **Never expose raw column names** from blocked datasets in the success path
- **Graceful degradation**: if scanning fails, returns CONDITIONAL (not crashes)

## 6. Demo Company Scan Flow

Demo companies provide pre-computed scan results for demonstration:
- `national-industrial-holdings` → READY (3,247 employees)
- `saudi-digital-services` → READY (1,850 employees)
- `riyadh-healthcare-network` → READY (4,120 employees)
- `gulf-retail-operations` → CONDITIONAL (6,800 employees, some warnings)
- `public-sector-workforce-authority` → READY (2,350 employees)

Each demo scan takes 1.8 seconds (simulated) to demonstrate scanning UX.

## 7. Real Upload (Production Mode)

In production, real file uploads POST to `/v1/tenants/{id}/upload/scan`. The current UI correctly shows the CONDITIONAL result with a "connect to backend" warning when running in frontend-only mode. This is honest behaviour — it does not pretend to scan successfully.

## 8. Audit Coverage

| Workflow Step | Tested | Test Reference |
|---------------|--------|----------------|
| File ingestion (all formats) | YES | Phase 9 tests |
| PII detection | YES | Phase 9 tests |
| Leakage detection | YES | Phase 9 tests |
| Dataset type classification | YES | Phase 10 tests 1–4 |
| Demo company scan | YES | Phase 9 tests |
| Upload blocked for missing tenant | YES | Phase 9 tests |
