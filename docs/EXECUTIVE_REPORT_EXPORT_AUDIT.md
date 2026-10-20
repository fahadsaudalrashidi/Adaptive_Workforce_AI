# Executive Report Export Audit — Phase 11

**Date:** 2026-05-21  
**Component:** `ExecutivePDFExporter`  
**Module:** `backend/core/executive_pdf_exporter.py`

---

## 1. Export Architecture Overview

The `ExecutivePDFExporter` generates self-contained HTML documents styled for enterprise executive distribution. Output is print-ready via `window.print()` / Ctrl+P in any modern browser — no third-party PDF library required.

```
Input:  report_type + tenant_id + data dict + language + demo_mode flag
Output: PDFExportResult (html_content, sha256_checksum, disclaimers_included, ...)
```

All HTML is self-contained with embedded CSS. No external fonts, images, or scripts are loaded. The output file is safe for air-gapped environments.

---

## 2. Report Types

| Type | Enum Value | Purpose | Estimated Pages |
|------|-----------|---------|----------------|
| Executive Summary | `executive_summary` | Board-level workforce intelligence overview | 5 |
| Governance Audit | `governance_audit` | PDPL & compliance deep-dive | 7 |
| Board Briefing | `board_briefing` | 2-page concise board pack | 2 |
| Data Readiness | `data_readiness` | Upload validation + schema audit results | 3 |
| Market Intelligence | `market_intelligence` | Job market summary (non-attrition datasets) | 3 |

---

## 3. Mandatory Disclaimer Enforcement

**All 3 disclaimers are included on every report, regardless of type, language, or demo mode.**

| Disclaimer | Key Text | Arabic Equivalent |
|------------|---------|-----------------|
| 1. Probabilistic Only | "PROBABILISTIC ANALYSIS ONLY: Risk scores... are NOT deterministic predictions about individual employees" | "تحليل احتمالي فقط" |
| 2. Governance Active | "GOVERNANCE CONTROLS ACTIVE: PII columns were excluded before analysis. Output does not contain employee identifiers." | "ضوابط الحوكمة نشطة" |
| 3. Offline Deployment | "OFFLINE DEPLOYMENT: Employee data does not leave the organisation's on-premises infrastructure." | "النشر دون اتصال" |

The `disclaimers_included` field of `PDFExportResult` always lists all three:
```python
disclaimers_included = [
    "probabilistic_analysis_only",
    "governance_controls_active",
    "offline_deployment",
]
```

Disclaimer placement: rendered on a page-break-separated section (`page-break-before: always`) after the main body, ensuring they appear on a dedicated page in print output.

---

## 4. Bilingual (EN/AR) Implementation

| Language Mode | Behaviour |
|--------------|-----------|
| `"en"` | English only; `dir="ltr"` on `<html>` |
| `"ar"` | English disclaimers + Arabic disclaimers; `dir="rtl"` on `<html>` |
| `"bilingual"` | All content + Arabic section headers and disclaimers |

Arabic-specific CSS:
- `.disclaimer-ar`: `text-align: right; direction: rtl` — RTL disclaimer block
- `.section-header-ar`: `text-align: right` — Arabic section header under English
- Arabic text rendered via Unicode; no font embedding required (system Arabic fonts used)

---

## 5. Security and Governance Controls

### 5.1 Tenant Validation
- Empty or whitespace-only `tenant_id` returns `success=False, error="tenant_id is required"` — never raises an exception
- No tenant-to-tenant data leakage possible (each call is stateless)

### 5.2 HTML Escaping
All user-supplied strings passed through `_escape()` before insertion into HTML:
```python
text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
```
Prevents XSS in any downstream browser rendering.

### 5.3 SHA-256 Integrity Checksum
Every export result carries a checksum of the HTML content:
```python
sha256_checksum = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
```
Allows recipients to verify report integrity after transmission.

### 5.4 No Employee-Level Data
By design:
- No row-level employee data is passed to the exporter
- Input data dict contains only aggregated KPIs (risk bands, stability index, calibration stats)
- Employee IDs, national IDs, emails are structurally absent from all report types

### 5.5 Demo Mode Banner
When `demo_mode=True`, a prominent amber banner is inserted before the page header:
```
DEMO MODE — Synthetic data only. Not representative of any real organisation.
```
CSS: amber background (`#fef3c7`), amber border (`#f59e0b`), bold weight — visually unmissable.

---

## 6. Report Content by Type

### Executive Summary
- KPI grid: total employees, stability index, organisation, AUC
- Risk band grid: Stable / Monitoring / Strategic Concern / Priority Review (colour-coded)
- Board-level summary text (EN + AR in bilingual mode)
- Strategic insights list (up to 6)
- Model reliability calibration box: AUC-ROC, ECE, Brier Score, Coverage@80%CI

### Governance Audit
- 6 governance control checklist: PDPL Compliance, Tenant Isolation, Leakage Protection, Audit Trail, Export Safety, Offline Mode
- Data protection controls table: 5 PDPL technical controls with mechanisms and status
- Legal caveat: "This audit does not constitute legal advice or guarantee PDPL certification."

### Board Briefing
- Condensed KPI grid: employees, stability index, organisation, PDPL compliance status
- Single executive summary text block
- Probabilistic scope statement

### Data Readiness
- KPI grid: rows, columns, readiness level, warning count
- Governance findings table (warnings, up to 10)

### Market Intelligence
- KPI grid: record count, analysis mode, mean salary, attrition modeling status
- Attrition blocked confirmation text
- Salary displayed as `SAR {amount:,.0f}` or "N/A" if not available

---

## 7. Print CSS

Print-specific CSS (`@media print`) ensures:
- Dark header backgrounds preserve colour (`-webkit-print-color-adjust: exact; print-color-adjust: exact`)
- Gradient logo background preserves in PDF
- Governance badge colours (green on dark) preserved
- `page-break-before: always` on disclaimer section — disclaimers always on their own page
- `page-break-inside: avoid` on header and meta sections — no mid-section breaks

---

## 8. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Empty `tenant_id` | Returns `success=False, error="tenant_id is required"`, no exception |
| `_build_body()` exception | Caught, returns `success=False, error=str(exc)`, logged at ERROR level |
| Missing data dict keys | `.get()` with defaults throughout — no KeyError possible |
| Non-string values passed | `_escape()` calls `str(text)` before processing |

---

## 9. Test Coverage (Phase 11 Tests 1–8)

| Test | What is verified |
|------|----------------|
| 1 | Executive summary: valid `<!DOCTYPE html>`, company name, employee count, stability index present |
| 2 | All 5 report types: all 3 disclaimers present; `disclaimers_included` list has length 3 |
| 3 | Bilingual mode: Arabic text present (`احتمالي` or `الحوكمة`) |
| 4 | SHA-256 checksum matches `hashlib.sha256(html_content.encode()).hexdigest()` |
| 5 | Empty `tenant_id`: returns `success=False`, error not None, `html_content == ""` |
| 6 | Demo mode: "DEMO MODE" and "Synthetic data" present in HTML |
| 7 | Governance audit: "PDPL", "Data Minimization", "Offline Mode Guard" / "OfflineModeGuard" present |
| 8 | Market intelligence: attrition "Blocked" visible; analysis mode present |
