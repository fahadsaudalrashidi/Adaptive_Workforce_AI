# PHASE 33.1 — EXPORT FLOW ROOT CAUSE FIX REPORT

**Date:** 2026-06-02  
**Version:** v2.3.1-enterprise  
**Status:** COMPLETE — all product export buttons now deliver Phase 33 outputs

---

## EXECUTIVE SUMMARY

The Phase 33 rebuild produced correct proof files, but the actual product UI buttons were delivering
wrong or stale exports. Root cause: the PDF button navigated to a Phase 26C React component instead
of calling the new Board Report V3 API endpoint. The PPTX button was correctly wired but its UI
description still showed stale 10-slide text. Both issues are now fixed.

---

## BROKEN FLOW FOUND

### PDF Export — Root Cause

| Step | What Was Happening | Status |
|------|-------------------|--------|
| User clicks PDF button | `onClick={() => onNavigate('executive-report-preview')}` | WRONG |
| Navigates to | `ExecutiveReportPreview.tsx` (Phase 26C inline React component) | WRONG |
| PDF generation | `window.print()` on Phase 26C HTML — not the Board Report V3 | WRONG |
| `/api/local/export/pdf` endpoint | Existed and correctly wired but **never called from UI** | ORPHANED |

The `ExecutiveReportPreview.tsx` component is a Phase 26C (legacy) report renderer:
- 7–9 pages depending on ML/simulation availability
- Dark navy header, dashboard-style card layout
- No Board Report V3 consulting document sections
- Does not use `executive_pdf_exporter.py` at all

### PPTX Export — Correctly Wired (not broken)

| Step | What Was Happening |
|------|-------------------|
| User clicks `.pptx` button | `handlePptx()` → `fetch POST /api/local/export/pptx` |
| Backend | `executive_pptx_exporter.generate_pptx()` → 12 slides (Phase 33) |
| Download | Binary `.pptx` blob, auto-downloaded |

The PPTX export was **already correctly wired** to the Phase 33 exporter. However:
- UI description said "10-slide Executive Board Deck" (stale)
- Slide outline showed 10 slides (stale — Phase 33 has 12)

---

## OLD EXPORTER PATHS (bypassed)

| Export | Old Path | Problem |
|--------|----------|---------|
| PDF | `ExecutiveReportPreview.tsx` → `window.print()` | Phase 26C React component, not consulting document |
| PPTX description | `pptContents[0]`: "10-slide Executive Board Deck" | Stale text, but export itself was correct |

---

## NEW EXPORTER PATHS (active)

| Export | New Path | Output |
|--------|----------|--------|
| PDF | `handleBoardPdf()` → `POST /api/local/export/pdf` → `ExecutivePDFExporter(BOARD_REPORT_V3)` → HTML in new window → `window.print()` | 11-section white consulting document, 50,184 chars |
| PPTX | `handlePptx()` → `POST /api/local/export/pptx` → `generate_pptx()` | 12-slide dark board deck, 53,621 bytes |
| HTML Deck | `handleSlides()` → `POST /api/local/export/slides` → `generate_slide_deck()` | 11-page white slide deck in new tab |

---

## FRONTEND FILES MODIFIED

### `executive-ui/src/pages/ExecutiveReports.tsx`

**Change 1 — New `handleBoardPdf` function (added after `handlePptx`):**
```typescript
const handleBoardPdf = async () => {
  if (!riskData) return
  try {
    const res = await fetch('/api/local/export/pdf', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...riskData, company_name: filename, report_type: 'BOARD_REPORT_V3' }),
    })
    const json = await res.json() as { success?: boolean; html_content?: string }
    if (json.success && json.html_content) {
      const win = window.open('', '_blank')
      if (win) {
        win.document.write(json.html_content)
        win.document.close()
        win.setTimeout(() => win.print(), 900)
      }
    }
  } catch { /* non-fatal */ }
}
```

**Change 2 — PDF button wired to `handleBoardPdf`:**
```tsx
// BEFORE:
onClick={() => onNavigate('executive-report-preview')}
// label: "Open Report Preview"

// AFTER:
onClick={handleBoardPdf}
disabled={!riskData}
// label: "Board Report PDF — Open & Print"
```

**Change 3 — Removed unused `onNavigate` from `ReportDeliveryCards` destructuring:**
```typescript
// BEFORE:
function ReportDeliveryCards({ riskData, filename, t, onNavigate }) { ... }

// AFTER:
function ReportDeliveryCards({ riskData, filename, t }) { ... }
// onNavigate kept in type signature (parent still passes it)
```

**Change 4 — PPT description updated to 12 slides:**
```typescript
// BEFORE:
'10-slide Executive Board Deck (one message per slide)'

// AFTER:
'12-slide Executive Board Deck (one message per slide)'
```

**Change 5 — PPT slide outline updated to 12 Phase 33 slides:**
```
01 · Cover — Financial Exposure Decision Teaser
02 · Executive Summary — Complete Picture
03 · Why Leadership Should Care — Business Continuity
04 · Workforce Stability — Proportional Risk Chart
05 · Financial Exposure — SAR Dominant Number
06 · Cost of Inaction — Monthly Accumulation
07 · Dept Hotspots — Financial Risk Table
08 · Retention Opportunity — Recovery Potential
09 · Strategic Priorities — Board Decisions
10 · Board Recommendation — Single Action
11 · Governance Assurance — PDPL + Confidence
12 · Closing — Decision Window
```

---

## BACKEND FILES MODIFIED

None. All backend routes were correctly wired in Phase 33:

| Endpoint | Handler | Exporter |
|----------|---------|----------|
| `POST /api/local/export/pdf` | `export_pdf()` in `local_analysis_routes.py:1409` | `ExecutivePDFExporter(BOARD_REPORT_V3)` |
| `POST /api/local/export/pptx` | `export_pptx()` in `local_analysis_routes.py:1381` | `executive_pptx_exporter.generate_pptx()` |
| `POST /api/local/export/slides` | `export_slide_deck()` in `local_analysis_routes.py:1352` | `executive_slide_exporter.generate_slide_deck()` |

---

## API ENDPOINTS VERIFIED

### PDF Endpoint Test
```
POST /api/local/export/pdf
Body: { total_employees: 800, priority_review_count: 94, company_name: "Saudi National Corp", report_type: "BOARD_REPORT_V3" }

Response:
  success: True
  html_content length: 50,184 chars
  page_count_estimate: 11
  report_type: BOARD_REPORT_V3
  has @media print: True
  has white background: True
  has "Board Intelligence Report" header: True
```

### PPTX Endpoint Test
```
generate_pptx() direct call (same function the endpoint uses)
  PPTX bytes: 53,621
  Slide count: 12 (confirmed via python-pptx + PowerPoint COM)
  python-pptx version: 1.0.2
```

---

## ACTUAL DOWNLOADED FILE PROOF

### Board Report V3 PDF (new product export)

**File:** `SCREENSHOTS/phase33_1_board_report_top.png`  
- White background (not dark dashboard)  
- "Board Intelligence Report — Executive Edition" header  
- **SAR 33.7M** financial exposure hero in red monospace  
- KPI strip: SAR 2.8M/month · SAR 11.8M savings · 281 at risk · Engineering highest-risk dept  
- Ruled narrative sections with consulting-style body text  
- 11 sections, PDPL-compliant footer  

**File:** `SCREENSHOTS/phase33_1_board_report_mid.png`  
- Leadership Situation Assessment section  
- The Situation + Key Leadership Finding (two-column ruled layout)  
- "Why Leadership Must Act Now" urgency box  

**File:** `SCREENSHOTS/phase33_1_board_report_bottom.png`  
- Department hotspots table  
- Financial exposure breakdown  
- Board recommendation section  

### Executive Board Deck PPTX (12 slides, product download)

**File:** `SCREENSHOTS/phase33_1_pptx_slide01.png` — Cover slide  
- Dark navy split-panel layout  
- "WORKFORCE RISK INTELLIGENCE REPORT"  
- SAR 33.7M right panel, SAR 2.8M/month, SAR 11.8M recovery  
- Footer: CONFIDENTIAL | 1/12  

**File:** `SCREENSHOTS/phase33_1_pptx_slide04.png` — Workforce Stability (proportional bars)  
- Proportional horizontal bar chart (not equal boxes)  
- Stable: 301, Monitoring: 218, Strategic Concern: 187, Priority Review: 94  
- Visual weight matches employee count (Phase 33 fix)  
- Footer: 4/12  

**File:** `SCREENSHOTS/phase33_1_pptx_slide06.png` — Cost of Inaction  
- Month 1: SAR 2.8M · Month 3: SAR 8.4M · Month 6: SAR 16.9M · Month 12: SAR 33.7M  
- "Every month without a board decision costs SAR 2.8M"  
- Recovery scenario: SAR 11.8M recovered · 78 retained  
- Footer: 6/12  

---

## BUILD & TEST RESULTS

```
npm run build
  ✓ tsc: 0 TypeScript errors
  ✓ vite build: 3.53s
  ✓ ExecutiveReports-DE4GaspQ.js: 79.46 kB

pytest tests/
  ✓ 1152 passed, 1 skipped, 0 failed
  ✓ 66.56s
```

---

## SUCCESS CRITERIA VERIFIED

| Criterion | Status |
|-----------|--------|
| PDF button calls Phase 33 Board Report V3 endpoint | ✅ |
| PDF opens white consulting document in new window with print dialog | ✅ |
| PDF uses real uploaded dataset results (riskData passed in body) | ✅ |
| PPTX button calls Phase 33 12-slide exporter | ✅ |
| PPTX downloads as real `.pptx` file (binary blob) | ✅ |
| PPTX opens in Microsoft PowerPoint (verified via COM, 12 slides) | ✅ |
| PPT slide outline updated to match Phase 33 (12 slides) | ✅ |
| Old Phase 26C `executive-report-preview` navigation removed from PDF button | ✅ |
| `npm run build`: 0 errors | ✅ |
| `pytest`: 1152 passed, 0 failed | ✅ |

---

## SCREENSHOTS GENERATED

| File | Contents |
|------|----------|
| `SCREENSHOTS/phase33_1_board_report_top.png` | Board Report V3 — cover + SAR hero + KPI strip |
| `SCREENSHOTS/phase33_1_board_report_mid.png` | Board Report V3 — narrative sections |
| `SCREENSHOTS/phase33_1_board_report_bottom.png` | Board Report V3 — department table + recommendations |
| `SCREENSHOTS/phase33_1_pptx_slide01.png` | PPTX Slide 1 — Cover (1/12) |
| `SCREENSHOTS/phase33_1_pptx_slide04.png` | PPTX Slide 4 — Workforce Stability proportional chart (4/12) |
| `SCREENSHOTS/phase33_1_pptx_slide06.png` | PPTX Slide 6 — Cost of Inaction timeline (6/12) |
| `SCREENSHOTS/phase33_1_pptx_slide10.png` | PPTX Slide 10 — Board Recommendation (10/12) |

---

## WHY PROOF FILES WERE CORRECT BUT PRODUCT EXPORT WAS WRONG

The proof scripts (`generate_proof.py`, `take_pdf_screenshot.mjs`) called the exporters directly:

```python
# generate_proof.py — called the exporter directly:
exporter.generate(report_type=PDFReportType.BOARD_REPORT_V3, ...)

# take_pdf_screenshot.mjs — screenshotted the proof HTML file:
await page.goto('file:///' + htmlPath)
```

These never went through the UI. The product UI had an independent code path:
- PDF button → React navigation → Phase 26C component → `window.print()` (no API call)
- This path was never changed in Phase 33

The fix closes the gap: the UI now calls the same API endpoint that the proof scripts tested.
