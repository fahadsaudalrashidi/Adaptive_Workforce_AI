# Demo Company Experience — Phase 9

**Document Type:** Product Reference  
**Phase:** 9  
**Date:** 2026-05-21  
**Audience:** Sales, Product, Customer Success, Pre-Sales Engineers

---

## Purpose

The Demo Company Experience provides five synthetic Saudi enterprise archetypes that can be used to demonstrate the full platform workflow — from file upload governance scan through executive report generation — without requiring real customer data.

All demo datasets are:
- Clearly labelled `DEMO_MODE = True` in code
- Generated deterministically (same seed → same output)
- Free of any real employee information
- Representative of realistic Saudi organizational profiles

---

## The Five Demo Companies

### 1. National Industrial Holdings Co. (الشركة الوطنية للصناعة القابضة)

| Attribute | Value |
|-----------|-------|
| Sector | Heavy Industry / الصناعات الثقيلة |
| Employees | 3,247 |
| Saudization | 62.4% |
| Avg. Tenure | 4.8 years |
| Base Attrition | 18% |
| Readiness | CONDITIONAL (67 duplicates) |

**Use case:** Mid-size industrial conglomerate. Shows how Operations and IT departments drive elevated stability indicators, while Finance and Legal are stable. Good for demonstrating the department risk heatmap and strategic insights.

---

### 2. Saudi Digital Services Group (مجموعة الخدمات الرقمية السعودية)

| Attribute | Value |
|-----------|-------|
| Sector | Technology & Telecoms |
| Employees | 1,850 |
| Saudization | 45.1% |
| Avg. Tenure | 2.9 years |
| Base Attrition | 28% |
| Readiness | READY |

**Use case:** Fast-growing tech company with high attrition in Software Engineering and Data & AI. Good for demonstrating JD-R construct dominance (job demands in tech roles) and Priority Review band placement.

---

### 3. Riyadh Healthcare Network (شبكة الرياض الصحية)

| Attribute | Value |
|-----------|-------|
| Sector | Healthcare |
| Employees | 4,120 |
| Saudization | 71.3% |
| Avg. Tenure | 5.6 years |
| Base Attrition | 14% |
| Readiness | READY |

**Use case:** Healthcare organization with high Saudization. Good for demonstrating stable workforce analytics, Nursing department monitoring indicators, and PDPL compliance narrative for sensitive sectors.

---

### 4. Gulf Retail Operations Ltd. (شركة عمليات التجزئة الخليجية)

| Attribute | Value |
|-----------|-------|
| Sector | Retail |
| Employees | 6,800 |
| Saudization | 38.7% |
| Avg. Tenure | 2.1 years |
| Base Attrition | 34% |
| Readiness | CONDITIONAL (high nulls, 312 duplicates) |

**Use case:** Large retail chain with high attrition, low Saudization, and data quality issues. Good for demonstrating the CONDITIONAL readiness path and recommended actions panel.

---

### 5. Public Sector Workforce Authority (هيئة القوى العاملة في القطاع العام)

| Attribute | Value |
|-----------|-------|
| Sector | Government |
| Employees | 2,350 |
| Saudization | 94.5% |
| Avg. Tenure | 8.3 years |
| Base Attrition | 7% |
| Readiness | READY |

**Use case:** Government organization with high stability and near-total Saudization. Good for demonstrating the Stable band majority and Vision 2030 workforce development alignment narrative.

---

## Technical Generation

**Module:** `backend/core/demo_company_generator.py`  
**Class:** `DemoCompanyGenerator`

```python
gen = DemoCompanyGenerator()

# Get list of profiles (for UI)
profiles = gen.list_profiles()

# Generate DataFrame for analysis
df = gen.generate("national-industrial-holdings", language="en")
df_ar = gen.generate("saudi-digital-services", language="ar")

# Generate raw bytes for upload/scan demo
raw_bytes, filename = gen.generate_bytes(
    "riyadh-healthcare-network",
    language="en",
    file_format="csv",
)
```

**Deterministic output:** Seeded with `numpy.random.default_rng(seed=42)`. Same company_id + seed always produces the same dataset.

**Language support:** `language="ar"` produces Arabic column headers (القسم, سنوات_الخدمة, etc.). `language="en"` produces English headers.

---

## React UI Integration

**File:** `executive-ui/src/data/demoCompanies.ts`

Exports:
- `DEMO_COMPANIES: DemoCompanyProfile[]` — 5 company profiles for card display
- `DEMO_SCAN_RESULTS: Record<string, DemoScanResult>` — Pre-computed scan results for UI demo (avoids requiring a live API connection)

The `DataUpload` page (`executive-ui/src/pages/DataUpload.tsx`) uses these to render demo company cards. Selecting a demo company simulates a 1.8-second governance scan and displays the scan result panel.

---

## Demo Mode Indicators

Every demo output is labelled:
- Python: `df.attrs["DEMO_MODE"] = True`
- API responses: `"demo_mode": true`
- HTML reports: amber `DEMO MODE` badge in report header
- UI: amber "DEMO MODE" banner in sidebar footer

These indicators cannot be removed. Demo mode is a platform-wide concept, not an optional display choice.

---

## What Demo Companies Do NOT Demonstrate

- Real PDPL compliance — demo data has no real PII to protect
- Actual Saudization compliance — values are illustrative only
- Calibrated predictions for any real organization
- Any claim about specific industries in Saudi Arabia

All demo outputs carry standard governance disclaimers noting the synthetic nature of the data.
