# Saudi Localization Audit — Phase 11

**Date:** 2026-05-21  
**Scope:** Bilingual (EN/AR) implementation across backend reports, frontend pages, and UI components

---

## 1. Localization Overview

The Adaptive Workforce AI platform is built for bilingual (English/Arabic) operation throughout. Saudi CHRO and CIO audiences expect Arabic support in executive materials. The platform implements RTL-aware layouts, Arabic section headers, bilingual disclaimers, and Arabic company names in all demo data.

---

## 2. Backend Localization — PDF Exporter

### 2.1 Language Modes

| Mode | Behavior |
|------|---------|
| `"en"` | English only; `<html lang="en" dir="ltr">` |
| `"ar"` | English body + Arabic disclaimers; `<html lang="ar" dir="rtl">` |
| `"bilingual"` | Full bilingual: English primary with Arabic section headers and all disclaimers in both languages |

### 2.2 Arabic Disclaimer Texts

Three mandatory disclaimers are translated in full:

**Disclaimer 1 — Probabilistic Analysis:**
> "تحليل احتمالي فقط: تمثل درجات المخاطر ومؤشرات الاستقرار توزيعات الاحتمال الإحصائية على مستوى المؤسسة والأقسام، وليست تنبؤات حتمية بشأن الموظفين الأفراد."

**Disclaimer 2 — Governance Active:**
> "ضوابط الحوكمة نشطة: صدر هذا التقرير في إطار منصة الذكاء التنفيذي للقوى العاملة. استُبعدت أعمدة البيانات الشخصية قبل التحليل. لا يتضمن الإخراج معرفات الموظفين أو الهويات الوطنية."

**Disclaimer 3 — Offline Deployment:**
> "النشر دون اتصال: تعمل هذه المنصة في وضع محلي أولاً دون اتصال بالإنترنت. لا تغادر بيانات الموظفين البنية التحتية المحلية للمؤسسة."

### 2.3 RTL CSS Implementation

Arabic disclaimer blocks use dedicated CSS class `.disclaimer-ar`:
```css
.disclaimer-ar {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #7c2d12;
  text-align: right;
  direction: rtl;
}
```

Arabic section headers use `.section-header-ar`:
```css
.section-header-ar {
  text-align: right;
  direction: rtl; /* inherited */
  border-bottom: 1px solid #e2e8f0;
}
```

HTML-level direction is set based on language mode:
```html
<html lang="ar" dir="rtl">   <!-- for "ar" mode -->
<html lang="en" dir="ltr">   <!-- for "en" or "bilingual" mode -->
```

---

## 3. Demo Data — Arabic Company Names

All 5 Saudi demo companies include both English and Arabic names, sourced from `demo_company_generator.py` and surfaced via `DemoDatasetManager.get_available_companies()`:

| Company ID | English Name | Arabic Name |
|-----------|-------------|------------|
| `national-industrial-holdings` | National Industrial Holdings | الشركة الوطنية للصناعة القابضة |
| `saudi-digital-services` | Saudi Digital Services | الخدمات الرقمية السعودية |
| `riyadh-healthcare-network` | Riyadh Healthcare Network | شبكة الرياض للرعاية الصحية |
| `gulf-retail-operations` | Gulf Retail Operations | عمليات تجزئة الخليج |
| `public-sector-workforce-authority` | Public Sector Workforce Authority | هيئة القوى العاملة في القطاع العام |

Arabic names are:
- Included in all PDF report headers when the company name is passed in the data dict
- Displayed in the frontend `DemoMode.tsx` company selection step
- Stored in `DemoDatasetResult.company_name_ar`
- Used in the executive summary bilingual KPI grid

---

## 4. Jadarat Market Demo — Arabic Dataset

The Jadarat demo dataset (`_generate_jadarat_demo()`) mimics Saudi job market posting structure with Arabic-region values:

| Field | Arabic-Aware Values |
|-------|-------------------|
| `region` | Riyadh, Jeddah, Dammam, Makkah, Madinah, Tabuk, Abha |
| `job_date` | Hijri-style date format: `DD/MM/144X` |
| `comp_type` | "Private", "Government", "Mixed" |
| `qualif` | "Bachelor's", "Diploma", "Master's", "High School" |

The `DemoDatasetResult` for Jadarat includes:
- `company_name_ar = "عرض سوق جدارات"`

Real Jadarat datasets use Arabic column headers (e.g., `المسمى الوظيفي`, `المنطقة`). The platform's `ExcelIngestionEngine` handles Arabic headers through the `_COLUMN_ALIAS_MAP` (35 entries) in `saudi_attrition_normalizer.py`.

---

## 5. Frontend Localization

### 5.1 TrustPanel.tsx

The Trust Dashboard displays 6 governance trust items. Labels are designed for bilingual audiences (English technical terms familiar to Saudi CIO/CHRO audiences). No full Arabic translation is built into the static component — this is appropriate for enterprise technical panels where English terminology is standard.

Trust items:
1. Governance Active
2. PDPL Compliance
3. Offline Deployment
4. Calibration Verified
5. Audit Logging Enabled
6. No External Data Transfer

### 5.2 DemoMode.tsx

The 10-step enterprise demonstration flow includes:
- Company selection showing both English and Arabic company names (from `DEMO_COMPANIES` data)
- Step descriptions that reference Saudi context: "Saudi CHRO", "PDPL compliance", "Saudization"
- Upload step mimics real Saudi enterprise workflow

### 5.3 DataUpload.tsx

The upload UI displays bilingual scanning messages during the 3-state flow (select → scanning → results). Scanning messages appear in both English and Arabic to communicate clearly to bilingual users.

---

## 6. Arabic Column Handling in Ingestion

The `ExcelIngestionEngine` and `saudi_attrition_normalizer.py` handle Arabic-header Excel files:

### Column Alias Map (35 entries)
Maps Arabic and misspelled English column names to canonical names used by the analysis pipeline. Examples:

| Input (Arabic/dirty) | Canonical |
|---------------------|----------|
| `الراتب` | `monthly_income` |
| `المسمى الوظيفي` | `job_role` |
| `القسم` | `department` |
| `سنوات الخبرة` | `years_at_company` |
| `الرضا الوظيفي` | `job_satisfaction` |
| `الاستنزاف` | `attrition` |

### NBSP and Whitespace Normalisation
Arabic Excel exports frequently include non-breaking spaces (`\xa0`) in column headers. The ingestion engine strips these before alias mapping:
```python
col.strip().replace('\xa0', ' ')
```

### Hijri Date Detection
Job date fields containing Hijri year ranges (1300–1600) are detected by `_is_hijri_date()` in `job_market_dataset_handler.py`. Detected Hijri dates are flagged but not converted to Gregorian — calendar variant ambiguity prevents safe conversion.

---

## 7. PDPL Terminology

The platform consistently uses Saudi PDPL-specific terminology in all executive documents:

| Term Used | Context |
|----------|---------|
| PDPL | Personal Data Protection Law (Saudi) — used throughout governance materials |
| Iqama | Saudi residency permit number — listed as PII trigger in SecureFileIngestion |
| Saudization | Saudi nationalisation ratio — reported in demo company profiles |
| SAR | Saudi Riyal — salary denomination in market intelligence reports |
| KSA | Kingdom of Saudi Arabia — deployment region reference |

---

## 8. Localization Coverage Summary

| Area | EN | AR | Bilingual |
|------|----|----|----------|
| PDF disclaimers | ✓ | ✓ | ✓ |
| PDF section headers | ✓ | ✓ | ✓ |
| Demo company names | ✓ | ✓ | ✓ |
| Arabic column ingestion | ✓ | ✓ | ✓ |
| Hijri date detection | — | ✓ | ✓ |
| Jadarat data format | — | ✓ | ✓ |
| Trust Panel | ✓ | — | — |
| Demo flow UI | ✓ | partial | partial |
| Scanning messages | ✓ | ✓ | ✓ |

Arabic-only and partial areas are appropriate for Phase 11. Full Arabic UI translation is a Phase 12+ deployment milestone (out of scope per Phase 11 rules).
