# Phase 14 — Employee Risk Dashboard Summary

**Status:** Complete  
**Date:** 2026-05-21

---

## What Was Built

Phase 14 adds a full **employee-level and department-level workforce risk dashboard** to the Adaptive Workforce Intelligence platform.

---

## New Files Created

### Backend

| File | Purpose |
|---|---|
| `backend/core/employee_risk_scoring.py` | Core scoring engine: per-record risk indicators, band assignment, department grouping, PII masking |
| `backend/core/employee_risk_exporter.py` | CSV export with governance disclaimer header and PII safety validation |

### Backend API (extended)

| Endpoint | Method | Description |
|---|---|---|
| `/api/local/upload/analyze-with-employees` | POST | Full pipeline: governance scan + employee-level scoring |

**Query parameters:** `page`, `page_size`, `risk_band`, `department`, `specialty`, `sort_by`, `sort_order`

### Frontend

| File | Purpose |
|---|---|
| `executive-ui/src/state/employeeRiskStore.ts` | TypeScript types, localStorage persistence for scored results |
| `executive-ui/src/pages/EmployeeRiskDashboard.tsx` | Full dashboard page with upload, KPIs, table, charts, drawer |

### Routing

| Change | Description |
|---|---|
| `src/types/index.ts` | Added `'employees'` to `NavPage` union type |
| `src/App.tsx` | Added `<EmployeeRiskDashboard />` to page router |
| `src/layout/Sidebar.tsx` | Added "Employee Risk Dashboard / تحليل الموظفين" nav item |

### Tests

| File | Tests |
|---|---|
| `tests/test_phase14_employee_risk_dashboard.py` | 20 tests covering all governance and scoring requirements |

### Documentation

| File | Content |
|---|---|
| `EMPLOYEE_LEVEL_RISK_GOVERNANCE.md` | Governance policy, PDPL alignment, technical enforcement |
| `EMPLOYEE_RISK_SCORING_METHOD.md` | Full methodology: theories, constructs, formula, weights |
| `DEPARTMENT_INTELLIGENCE_DASHBOARD.md` | Department grouping, visualisations, export format |
| `PHASE14_EMPLOYEE_RISK_DASHBOARD_SUMMARY.md` | This file |

---

## Feature Specification

### After Uploading Saudi Attrition XLSX

1. Navigate to **Employee Risk Dashboard** in the sidebar
2. Upload the same dataset file
3. Dashboard shows:
   - **1,191 records analyzed** (for the standard Saudi dataset)
   - KPIs: total records, average risk indicator, priority review count, highest-risk department, governance status
   - Risk band distribution (Stable / Monitoring / Strategic Concern / Priority Review)
   - Stacked department bar chart
   - Searchable, filterable, sortable employee risk table
   - Expandable department intelligence cards
   - Individual employee safe profile drawer (click any row)

### Safety Properties

- ✅ All employee IDs masked (SHA-256 hash prefix → EMP-XXXXXX)
- ✅ PII columns (name, email, phone, national_id) stripped before scoring
- ✅ No deterministic language ("will resign", "guaranteed attrition")
- ✅ Every output includes governance disclaimer
- ✅ CSV export includes mandatory disclaimer header
- ✅ Fully local and offline — no network calls
- ✅ No server-side persistence of employee data

---

## Scoring Algorithm Summary

**Construct-based:** Matches Saudi HR columns (OverTime, Physical_Stress, Job_Satisfaction, etc.) to 21 validated theoretical constructs from COR, JD-R, FFM, Mobley, and Adams Equity theories.

**Formula:**
```
risk_score = 30 + Σ(risk_weights) - 0.6×Σ(protective_weights) + jitter(±3)
stability_score = 100 - risk_score + jitter(±2)
```

**Bands:**
- Stable: 0–30
- Monitoring: 30–55
- Strategic Concern: 55–75
- Priority Review: 75–100

---

## Non-Negotiable Constraints (All Preserved)

- ✅ Governance and PDPL warnings active
- ✅ No fake/demo employee rows
- ✅ Fully local and offline
- ✅ No login/auth/cloud
- ✅ No multi-tenant logic
- ✅ No raw employee identifiers in output
- ✅ Non-deterministic language throughout

---

## Test Results

Run with: `pytest tests/test_phase14_employee_risk_dashboard.py -v`

Expected: **20/20 tests pass**

Key tests:
- One scored record per row
- Scores in [0, 100]
- Bands are valid strings
- PII excluded from output
- Department totals = total records
- Band counts = total records
- Job posting dataset → 0 matched constructs
- Pagination limits records correctly
- Band filter works
- Governance disclaimer in all exports
