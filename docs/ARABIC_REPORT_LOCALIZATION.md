# Arabic Report Localization — Phase 9

**Document Type:** Localization Reference  
**Phase:** 9  
**Date:** 2026-05-21  
**Audience:** Product, Engineering, Content Review

---

## Scope

This document describes the bilingual (Arabic / English) localization system for all executive reports, governance notices, and UI labels produced by the Adaptive Workforce Intelligence platform.

---

## Architecture

### ReportLocalizer

**Module:** `backend/core/report_localization.py`  
**Class:** `ReportLocalizer(language: 'en' | 'ar')`

```python
loc = ReportLocalizer("ar")
title = loc.label("report_executive_summary")
# → "تقرير الملخص التنفيذي"

disclaimer = loc.governance_disclaimer()
# → Full Arabic governance disclaimer text

layout = loc.pdf_layout()
# → {"direction": "rtl", "text_align": "R", "font_family": "arial", ...}
```

### BilingualString

All strings are stored as `BilingualString(en=..., ar=...)` dataclasses. Access via `.get(language)`.

---

## Arabic Authoring Principles

1. **No machine translation** — All Arabic text is hand-authored to reflect the precise legal and technical meaning of the governance notices.

2. **Legal equivalence** — The Arabic PDPL note carries the same legal disclaimers as the English version. The phrase "لا تُصادق هذه المنصة على الامتثال القانوني" is a precise translation of "This platform does not certify legal compliance" and cannot be softened.

3. **RTL layout** — Arabic reports set `dir="rtl"` on the root HTML element and use right-aligned tables and text. PDF layout uses `text_align: "R"` and `header_align: "R"`.

4. **Font** — Arabic UI uses the Cairo font family. Arabic PDF reports fall back to system Arabic fonts where Cairo is unavailable.

5. **Numerics** — Numeric values (scores, percentages, row counts) are rendered in Western Arabic numerals (0–9) for cross-audience compatibility.

---

## Governance Notice Coverage

All three mandatory disclaimers exist in both languages:

| Notice | English Key | Arabic Content |
|--------|-------------|---------------|
| Governance Disclaimer | `GOVERNANCE_DISCLAIMER.en` | `GOVERNANCE_DISCLAIMER.ar` |
| Confidence Warning | `CONFIDENCE_WARNING.en` | `CONFIDENCE_WARNING.ar` |
| PDPL Review Note | `PDPL_NOTE.en` | `PDPL_NOTE.ar` |

The Arabic PDPL note explicitly names the Saudi Personal Data Protection Law (نظام حماية البيانات الشخصية) and its Royal Decree reference (المرسوم الملكي م/19).

---

## Label Coverage

The `LABELS` dict in `report_localization.py` covers:

| Category | Count |
|----------|-------|
| Report titles | 4 |
| Section headers | 9 |
| Risk band labels | 4 |
| KPI labels | 5 |
| Table column headers | 5 |
| Theory names | 5 |
| Common UI strings | 11 |

**Total: 43 bilingual label pairs**

---

## Theory and Construct Labels

| Construct (EN) | Construct (AR) |
|----------------|---------------|
| Satisfaction Index | مؤشر الرضا |
| Burnout Risk | مخاطر الإرهاق |
| Engagement Score | درجة الالتزام |
| Career Progression | التقدم الوظيفي |
| Salary Growth | نمو الراتب |
| Tenure Ratio | نسبة الأقدمية |
| Income Per Level | الدخل حسب المستوى |

| Theory (EN) | Theory (AR) |
|-------------|------------|
| Conservation of Resources Theory (COR) | نظرية الحفاظ على الموارد (COR) |
| Job Demands-Resources Model (JD-R) | نموذج متطلبات الوظيفة والموارد (JD-R) |
| Five Factor Model (FFM) | نموذج العوامل الخمسة الكبرى (FFM) |
| Mobley Turnover Process | نموذج موبلي لعملية التحويل الوظيفي |
| Adams Equity Theory | نظرية العدالة لآدامز |

---

## React UI Localization

The executive React UI uses `LanguageContext` with:
- `t(en, ar)` helper for inline translations
- `isAr` boolean for conditional rendering (Arabic-first content)
- `dir="rtl"` applied to `document.documentElement` when Arabic is active
- Cairo font loaded from Google Fonts via CSS import when Arabic is selected

All 5 dashboard pages, the DataUpload page, and all shared components support bilingual rendering.

---

## What is NOT Machine Translated

The following content was authored entirely in Arabic and never machine-translated:
- All three governance disclaimers
- Risk band labels and descriptions
- All 43 LABELS dict values
- Demo company names, department names, and descriptions
- Strategic insight text in demo workforce data
- Demo company Arabic column headers

Any future additions to `LABELS` or `DEMO_WORKFORCE_METRICS` must follow the same hand-authoring principle.
