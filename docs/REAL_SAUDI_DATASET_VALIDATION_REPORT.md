# Real Saudi Dataset Validation Report — Phase 10

**Date:** 2026-05-21  
**Phase:** 10 — Real Saudi Dataset Validation & Upload-to-Report Hardening  
**Status:** VALIDATION COMPLETE — All 4 datasets processed, governance rules enforced

---

## 1. Validation Scope

Four real Saudi datasets were acquired and tested against the full upload-to-report pipeline:

| Dataset | Source | Rows | Columns | Type |
|---------|--------|------|---------|------|
| Original Dataset of Employee Attrition (1).xlsx | Saudi HR organisation | 1,191 | 35 | Employee attrition HR |
| Jadarat_data12.csv | Jadarat Saudi job portal | 1,470 | 18 | Job market postings |
| processed_dataset.csv | Processed Jadarat extract | 1,470 | 14 | Cleaned job market |
| Job Posting.csv | Global aggregator (stress test) | 9,919 | 21 | Global postings |

---

## 2. Dataset 1 — Saudi Employee Attrition Excel

**File:** `Original Dataset of Employee Attrition (1).xlsx`  
**Classification:** `EMPLOYEE_ATTRITION_DATASET` (confidence ≥ 0.83)  
**Dashboard mode:** `workforce_stability`  
**Attrition modeling:** PERMITTED

### Ingestion challenges identified and resolved

| Challenge | Resolution |
|-----------|-----------|
| Leading-space column names (`"Gender "`) | Stripped by `_COLUMN_ALIAS_MAP` |
| Leading-space in column names (`" Maritalstatus"`) | Stripped by `_COLUMN_ALIAS_MAP` |
| Non-breaking space prefix (`"\xa0Academic_degree "`) | NBSP stripped before lookup |
| Internal space in column name (`"Get_ Deserved_Promotion"`) | Explicit alias mapping |
| Internal space in column name (`"Work_Live_Balance"`) | Mapped to `work_life_balance` |
| Attrition values with leading space (`" Yes"`, `" No"`) | `.strip().lower()` before mapping |
| Salary ranges as text (`"From 5000 to 10000 S.R"`) | Regex parsed to (min, max, midpoint) |
| Pandas 3.0 `str` dtype (not `object`) | `pd.api.types.is_string_dtype()` check |

### Normalisation output

- **Columns renamed:** 35 of 35 mapped to canonical names
- **Attrition binary:** 1,191 rows normalised — 0 unparseable values
- **Attrition distribution:** `Yes` = 1, `No` = 0 (exact mapping confirmed)
- **Salary midpoints:** Computed for all rows with `"From X to Y S.R"` format
- **Proxy constructs available:** 8 of 8

### Proxy construct availability

| Construct | Theory | Required columns | Status |
|-----------|--------|-----------------|--------|
| BurnoutRisk_Proxy | COR | physical_stress, psychological_exhaustion, health_issues | AVAILABLE |
| SatisfactionIndex_Proxy | COR | job_satisfaction, environment_satisfaction, rewards_wages_satisfaction, work_life_balance | AVAILABLE |
| EngagementScore_Proxy | COR | job_engagement, emotional_commitment | AVAILABLE |
| CareerProgression_Proxy | JD-R | get_deserved_promotion, training_programs_during_last_three_years, useful_training_programs | AVAILABLE |
| SalaryGrowth_Proxy | JD-R | monthly_salary_range, allowances, bonus, medical_insurance | AVAILABLE |
| TenureRatio_Proxy | JD-R | years_experience, years_in_current_org | AVAILABLE |
| WithdrawalPressure_Proxy | Mobley | job_opportunities, job_stability, distance_to_work | AVAILABLE |
| PerceivedEquity_Proxy | Adams | get_deserved_promotion, payment_overtime, rewards_wages_satisfaction | AVAILABLE |

**PROXY LABEL MANDATORY:** All 8 constructs are labelled `proxy=True`. These are NOT validated psychometric instruments. They are organisational-theory-grounded signal proxies derived from available Saudi HR columns.

---

## 3. Dataset 2 — Jadarat Arabic Job Postings

**File:** `Jadarat_data12.csv`  
**Encoding:** UTF-8-BOM (`utf-8-sig`)  
**Classification:** `JOB_MARKET_POSTING_DATASET`  
**Dashboard mode:** `market_intelligence`  
**Attrition modeling:** BLOCKED

### Ingestion results

- **Hijri date column detected:** `job_date` (format `DD/MM/14XX`, year range 1440–1445)
- **Salary extraction:** From `benefits` field (list-like text `['Salary', '5000.0']`)
- **Position slots:** Parsed from `positions` column (`"0 / 3"` → filled=0, total=3)
- **Experience:** Parsed from `exper` column (`"3 Years"` → 3.0)
- **Sensitive columns:** `comp_name`, `comp_no` excluded from executive outputs

### Governance enforcements

- Attrition modeling BLOCKED — dataset contains vacancy postings, not employee records
- Hijri dates recognised but NOT converted to Gregorian (calendar variant ambiguity)
- `comp_name` flagged as sensitive — company identifiers excluded from public-facing reports
- No Saudi workforce stability conclusions generated

---

## 4. Dataset 3 — Processed Job Market (Cleaned)

**File:** `processed_dataset.csv`  
**Encoding:** UTF-8-BOM (`utf-8-sig`)  
**Classification:** `JOB_MARKET_POSTING_DATASET`  
**Dashboard mode:** `market_intelligence`  
**Attrition modeling:** BLOCKED

### Ingestion results

- **Salary column:** Numeric (`float64`) — read directly, no text parsing required
- **Sensitive columns:** `comp_name` detected and excluded
- **Market summary:** Regional distribution and top job titles extracted

### Governance enforcements

- No attrition target column exists — attrition prediction not permitted
- `comp_name` excluded — company names are commercially sensitive identifiers
- Analysis limited to market intelligence: salary ranges, regional distribution, job categories

---

## 5. Dataset 5 — Large Global Job Posting Stress Test

**File:** `Job Posting.csv`  
**Encoding:** cp1256 (Windows Arabic code page) — UTF-8 attempts fail  
**Classification:** `GLOBAL_JOB_POSTING_STRESS_TEST`  
**Row count:** 9,919  
**Dashboard mode:** `ingestion_stress_test`  
**Attrition modeling:** BLOCKED

### Ingestion results

- **Encoding:** cp1256 required (auto-detected by `ExcelIngestionEngine` fallback chain)
- **Salary null rate:** ~94.2% — salary statistics unreliable, warning generated
- **Stress test validated:** Large CSV ingestion with mixed encodings, null-heavy fields, long text columns

### Governance enforcements

- Explicitly classified as GLOBAL stress test — NOT Saudi workforce data
- No Saudi workforce conclusions generated from this file
- Salary statistics flagged as unreliable (94% null rate)
- Warning attached to all outputs: `"STRESS TEST MODE: No Saudi workforce conclusions should be drawn"`

---

## 6. Cross-Dataset Governance Summary

| Rule | Status |
|------|--------|
| Attrition modeling blocked for non-employee datasets | ENFORCED |
| Job posting data never treated as employee records | ENFORCED |
| No fake stability scores for blocked datasets | ENFORCED |
| Sensitive columns (comp_name) excluded from exec outputs | ENFORCED |
| Hijri dates recognised, conversion deferred | ENFORCED |
| Proxy construct labels (PROXY=True) on all constructs | ENFORCED |
| Employee data offline-only (OfflineModeGuard) | ENFORCED |
| PDPL proxy warning on all attrition outputs | ENFORCED |

---

## 7. Test Coverage

16 Phase 10 tests written and passing in `tests/test_phase10_real_saudi_datasets.py`.  
Full test suite: **481 tests passing, 0 failures** (was 465 before Phase 10).

---

*This report documents real dataset validation findings. All datasets were processed locally without any data leaving the test environment.*
