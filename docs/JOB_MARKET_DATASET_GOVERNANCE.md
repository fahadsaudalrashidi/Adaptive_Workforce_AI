# Job Market Dataset Governance — Phase 10

**Date:** 2026-05-21  
**Scope:** All non-employee datasets processed by `job_market_dataset_handler.py`  
**Applies to:** Jadarat_data12.csv, processed_dataset.csv, Job Posting.csv

---

## 1. Governance Principle

Job market posting datasets and employee HR datasets are **categorically different data types** that require different analysis modes, different governance controls, and different output constraints.

Mixing these types — treating a job vacancy record as an employee record, or running attrition models on posting data — constitutes a scientific and governance failure. This document defines the rules that prevent such failures.

---

## 2. Dataset Type Taxonomy

| Type | Description | Permitted Analysis | Blocked Analysis |
|------|-------------|-------------------|-----------------|
| `EMPLOYEE_ATTRITION_DATASET` | Employee-level HR records with behavioral signals | Attrition modeling, theory constructs, workforce stability | None |
| `JOB_MARKET_POSTING_DATASET` | Vacancy postings (what employers want) | Market intelligence, salary ranges, regional demand | Attrition modeling, stability scoring |
| `GLOBAL_JOB_POSTING_STRESS_TEST` | Large global aggregated postings | Ingestion stress testing only | All analytical outputs |
| `GOVERNMENT_WORKFORCE_TABLE` | Aggregate statistics (GASTAT/Nitaqat) | Market trend analysis | Individual-level modeling |
| `UNKNOWN_OR_UNSUPPORTED` | Unclassifiable dataset | None | All |

---

## 3. Classification Method

Classification is **column-signal-based**, not filename-based. This prevents misclassification from renamed files.

### Scoring algorithm

**Employee attrition score:** `target_hits * 5 + behavioral_hits * 2 + demographic_hits * 1`
- Target signals: `attrition`, `turnover`, `left`, `resigned`, `churn`
- Behavioral signals: `job_satisfaction`, `emotional_commitment`, `psychological_exhaustion`, etc.
- Demographic signals: `age`, `gender`, `marital_status`, `department`, etc.

**Job posting score:** `posting_hits * 2` (+ 5 bonus if large dataset >5,000 rows and score >6)
- Posting signals: `job_date`, `comp_name`, `comp_no`, `positions`, `exper`, `benefits`, etc.

**Decision rule:**
- Attrition score ≥ 8 and > job posting score → `EMPLOYEE_ATTRITION_DATASET`
- Job posting dominant + >5,000 rows + score ≥ 10 → `GLOBAL_JOB_POSTING_STRESS_TEST`
- Job posting dominant + score ≥ 4 → `JOB_MARKET_POSTING_DATASET`
- Weak signals → `UNKNOWN_OR_UNSUPPORTED`

---

## 4. Attrition Modeling Prohibition — Enforcement

For all non-employee datasets, attrition modeling is **permanently blocked** at the handler level. The block reason is included in every result object:

```
"This dataset is classified as a job market posting dataset.
It contains vacancy/posting records, not employee-level HR behavioral data.
Attrition modeling, flight-risk scoring, and workforce stability predictions
are not permitted for this dataset type."
```

This block cannot be overridden by the caller. The `JobMarketHandlingResult` always has:
- `attrition_blocked = True`
- `analysis_mode = "market_intelligence"`

---

## 5. Sensitive Column Governance

The following column types are treated as sensitive in job market datasets and excluded from executive-facing outputs:

| Column Pattern | Reason |
|---------------|--------|
| `comp_name` / `company_name` | Employer identity — commercially sensitive |
| `comp_no` / `company_number` | Government registration — not for public reports |
| `national_id` / `iqama` | Personal identity document numbers |
| `email` / `phone` / `mobile` | Direct contact information |
| `employee_id` / `emp_id` | Individual identifiers |

These are detected at ingestion and listed in `sensitive_columns_detected`. They are never passed to executive report generators.

---

## 6. Dataset-Specific Rules

### Jadarat (Saudi job portal)

- Hijri dates in `job_date` are recognised but not converted (calendar variant ambiguity)
- Salary must be extracted from `benefits` list field — no dedicated salary column exists
- `comp_name` and `comp_no` are sensitive — excluded from all outputs
- Position slot analysis (`positions` column: `"N / M"`) is permitted
- Experience requirement analysis (`exper` column: `"N Years"`) is permitted

### Processed Dataset

- Numeric salary column (`salary`) is read directly — no text parsing required
- `comp_name` is sensitive — excluded from executive outputs
- No attrition target column exists — attrition prediction cannot proceed regardless of classification
- Analysis limited to: salary distribution, regional breakdown, job title frequency

### Job Posting.csv (Global stress test)

- Encoding: cp1256 (Windows Arabic) — not UTF-8
- ~94.2% salary null rate — salary statistics must carry `unreliable` flag
- Not Saudi workforce data — no Saudi-specific conclusions permitted
- Purpose: ingestion robustness and encoding resilience testing only
- Warning attached to all outputs: "STRESS TEST MODE"

---

## 7. Market Intelligence Output Constraints

All job market outputs must satisfy:

1. **No stability scores** — no flight-risk percentages, no attrition predictions
2. **No employee-level segments** — outputs describe the market, not individuals
3. **No theory constructs** — COR/JD-R/Mobley/Adams not applied to posting data
4. **Sensitive columns excluded** — comp_name, comp_no never in reports
5. **Unreliable data flagged** — high null rates, Hijri dates, encoding assumptions noted
6. **Saudi-specific conclusions restricted** — global datasets cannot generate Saudi claims

---

## 8. Dashboard Mode Mapping

| Dataset Type | Dashboard Mode |
|-------------|---------------|
| `EMPLOYEE_ATTRITION_DATASET` | `workforce_stability` |
| `JOB_MARKET_POSTING_DATASET` | `market_intelligence` |
| `GLOBAL_JOB_POSTING_STRESS_TEST` | `ingestion_stress_test` |
| `GOVERNMENT_WORKFORCE_TABLE` | `government_workforce` |
| `UNKNOWN_OR_UNSUPPORTED` | `blocked` |

Dashboard mode is set at classification time and cannot be overridden by downstream modules.

---

## 9. Governance Certification

| Control | Implemented | Tested |
|---------|------------|--------|
| Type classification (column-signal-based) | `dataset_type_classifier.py` | tests 1–4 |
| Attrition block for job market datasets | `job_market_dataset_handler.py` | tests 9–12 |
| Sensitive column detection | `job_market_dataset_handler.py` | tests 9–10 |
| Hijri date recognition | `job_market_dataset_handler.py` | test 9 |
| Stress-test warning | `job_market_dataset_handler.py` | test 11 |
| market_intelligence mode enforcement | `job_market_dataset_handler.py` | tests 9–12 |
| Salary null rate warning (>80%) | `job_market_dataset_handler.py` | test 11 |

*All 481 tests passing as of Phase 10 completion.*
