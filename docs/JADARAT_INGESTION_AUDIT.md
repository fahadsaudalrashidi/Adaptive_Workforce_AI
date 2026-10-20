# Jadarat Dataset Ingestion Audit — Phase 10

**Date:** 2026-05-21  
**Dataset:** Jadarat_data12.csv  
**Handler:** `backend/core/job_market_dataset_handler.py` (subtype: `JADARAT_SAUDI_POSTINGS`)  
**Analysis mode:** Market Intelligence ONLY

---

## 1. Dataset Overview

Jadarat is Saudi Arabia's national job portal operated by the Human Resources Development Fund (HRDF). The `Jadarat_data12.csv` file contains 1,470 job posting records scraped from the platform.

| Property | Value |
|---------|-------|
| Rows | 1,470 |
| Columns | 18 |
| Encoding | UTF-8-BOM (`utf-8-sig`) |
| Language | Arabic + English mixed |
| Date format | Hijri calendar (`DD/MM/14XX`) |
| Salary representation | Embedded in `benefits` list field |

---

## 2. Column Inventory

| Column | Type | Notes |
|--------|------|-------|
| `job_title` | text | Arabic/English job titles |
| `job_date` | text | **Hijri dates** — e.g., `"27/05/1444"` |
| `comp_name` | text | **SENSITIVE** — company name |
| `comp_no` | text | **SENSITIVE** — company registration number |
| `comp_type` | categorical | Company type (government/private) |
| `comp_size` | categorical | Employee count range |
| `eco_activity` | text | Economic activity / sector |
| `qualif` | categorical | Required qualification level |
| `contract` | categorical | Contract type (full-time/part-time) |
| `positions` | text | Format: `"filled / total"` (e.g., `"0 / 3"`) |
| `exper` | text | Format: `"N Years"` (e.g., `"3 Years"`) |
| `region` | text | Saudi region (Riyadh, Makkah, etc.) |
| `city` | text | City name |
| `benefits` | text | List-like field: `"['Salary', '5000.0']"` |
| `gender` | categorical | Required gender |
| `nationality` | categorical | Required nationality |
| `age` | text | Age requirement |
| `disability` | categorical | Disability accommodation |

---

## 3. Hijri Date Handling

**Detection:** The `job_date` column contains dates with year values in the range 1440–1445, which fall within the Hijri calendar (1300–1600 is the detection range).

**Detection method:** Regex pattern `r"\b(\d{1,2})[/\-](\d{1,2})[/\-](1[34]\d{2})\b"` with year range check.

**Policy:** Hijri dates are **recognised but NOT converted** to Gregorian dates.

**Reason:** Hijri calendar conversion requires specification of which Hijri calendar variant is in use (Umm al-Qura, tabular, etc.). Incorrect conversion could introduce systematic date errors. The safest approach is to preserve raw dates and flag the column.

**Future recommendation:** If date-based trend analysis is required, integrate the `hijri-converter` Python library with Umm al-Qura calendar tables (official Saudi calendar).

---

## 4. Salary Extraction from Benefits Field

The `benefits` column contains list-like text strings rather than a dedicated numeric salary field.

**Format examples:**
```
"['Salary', '5000.0']"
"['Housing', 'Transportation', 'Salary', '8000.0']"
"['Housing', 'Transportation']"
```

**Extraction method:** Regex search for numeric values ≥ 100 SAR within strings containing `"Salary"` or `"راتب"`.

**Limitations:**
- If salary does not appear as the string `"Salary"`, it is not extracted
- Salary values are point estimates (not ranges)
- Some postings do not offer a specified salary — these yield `null`
- Non-salary benefits (housing allowance amounts) are not currently separated

---

## 5. Position Slot Parsing

**Column:** `positions`  
**Format:** `"filled / total"` e.g., `"0 / 3"`, `"2 / 5"`

**Parsing:** Regex `r"(\d+)\s*/\s*(\d+)"` extracts (filled, total).  
**Computed field:** `open_slots = total - filled` (summed across dataset)

---

## 6. Experience Requirement Parsing

**Column:** `exper`  
**Format:** `"N Years"` e.g., `"0 Years"`, `"3 Years"`, `"5 Years"`  
**Parsing:** Regex `r"(\d+(?:\.\d+)?)\s*[Yy]ears?"` extracts numeric value.  
**Computed field:** Mean experience required across all postings.

---

## 7. Sensitive Column Governance

The following columns are **excluded from all executive-facing outputs**:

| Column | Reason |
|--------|--------|
| `comp_name` | Company name is commercially sensitive; could identify employers without consent |
| `comp_no` | Government registration number — not for public dissemination in reports |

These columns are available in raw ingestion but stripped from any report, export, or dashboard widget.

---

## 8. Attrition Modeling Prohibition

**HARD BLOCK:** Jadarat is a job vacancy dataset. It contains what employers are looking for — not what employees feel or do.

The following analyses are **explicitly prohibited** for Jadarat data:
- Attrition prediction or flight-risk scoring
- Turnover probability estimation
- Workforce stability scoring
- Theory-grounded construct computation (COR/JD-R/FFM/Mobley/Adams)
- Employee-level segmentation

**Reason:** Jadarat records represent a posted vacancy at a point in time. There is no employee, no tenure, no satisfaction score, and no attrition outcome. Applying attrition models to this data would produce meaningless and misleading outputs.

---

## 9. Permitted Analysis (Market Intelligence Mode)

The following analyses are permitted and appropriate for Jadarat data:

- Regional vacancy distribution (by region, city)
- Sector demand analysis (eco_activity distribution)
- Most-posted job titles
- Salary range analysis (from extracted benefits data)
- Experience requirement distribution
- Position availability (filled vs. open slots)
- Contract type breakdown (full-time vs. part-time)
- Qualification demand analysis

---

## 10. Audit Summary

| Item | Result |
|------|--------|
| Rows ingested | 1,470 |
| Encoding | utf-8-sig |
| Hijri dates detected | YES — job_date column |
| Salary extracted | YES — from benefits field |
| Position slots parsed | YES |
| Experience parsed | YES |
| Sensitive columns flagged | comp_name, comp_no |
| Attrition modeling | BLOCKED |
| Analysis mode | market_intelligence |
| Test coverage | test_09_jadarat_handling |
