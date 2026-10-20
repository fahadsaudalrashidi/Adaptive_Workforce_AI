# Onboarding Wizard Design — Phase 9

**Document Type:** Product Design Reference  
**Phase:** 9  
**Date:** 2026-05-21  
**Audience:** Product, UX, Engineering

---

## Overview

The Data Upload page (`executive-ui/src/pages/DataUpload.tsx`) implements a self-guided onboarding experience for enterprise HR data ingestion. It is designed for CHROs and HR administrators who may not be technical — the governance scanning process is presented as a transparent, trustworthy verification step rather than a technical barrier.

---

## Three-Step Flow

```
Step 1: SELECT          Step 2: SCANNING         Step 3: RESULTS
────────────────        ────────────────         ────────────────
Demo company cards      Animated spinner         Readiness banner
  OR                    Progress text            KPI grid
File upload drop zone   "Checking for PII…"      Issue panels
                        "Scanning columns…"      Recommendations
```

### Step 1: SELECT

Two tabs:
1. **Demo Companies** (default) — 5 cards, one per Saudi enterprise archetype
2. **Upload File** — Drag-and-drop zone accepting .xlsx, .xls, .csv, .parquet, .json

The demo companies tab is the default because it allows a full demonstration experience without requiring a real data file. This is the primary path for enterprise evaluation and sales demos.

**Demo Company Cards** include:
- Sector badge (color-coded)
- Company name (Arabic or English based on language toggle)
- Description (bilingual)
- Employee count, Saudization percentage

### Step 2: SCANNING

Animated spinner with three progress messages:
- "Checking for PII"
- "Scanning leakage columns"
- "Assessing data quality"

Scan duration: 1.8 seconds for demo, actual API response time for real files.

The scan step exists even for demo companies — it reinforces the governance narrative that every file goes through the same scanning process.

### Step 3: RESULTS

**Readiness Banner:**
- READY → Emerald (✓ All governance checks passed)
- CONDITIONAL → Amber (⚠ Review Warnings)
- BLOCKED → Red (✗ Cannot Proceed)

**Data Quality KPIs:** Row count, column count, feature column count, language detection

**ERP Detection Notice** (if detected): blue info bar

**PII/Leakage Issues Panel** (if present): red panel listing blocked columns

**Blocking Reasons** (if any): red listed items

**Warnings** (if any): amber listed items

**Recommended Actions** (if any): numbered action list

**All Clear** (READY only): green confirmation panel

---

## Governance UX Principles

1. **Transparency** — Every blocking reason is explained in plain English/Arabic. Users are told exactly which column caused the block and why.

2. **No silent failures** — A BLOCKED result does not show an error page; it shows a structured governance result with actionable recommendations.

3. **PDPL education** — Each scan result includes a PDPL note explaining why PII detection exists and what to do next.

4. **Demo mode visibility** — Demo company datasets are clearly labelled. Users cannot accidentally use demo data as if it were real.

5. **Reversibility** — "Scan another" button allows returning to Step 1 without page refresh.

---

## Bilingual Support

Both tabs, all card content, all scan messages, and all result panels are translated:
- English: `t('Scan another', 'فحص آخر')` → "Scan another"
- Arabic: → "فحص آخر"

Company names use `isAr ? profile.name_ar : profile.name_en` pattern.

---

## What the Wizard Does NOT Do

- **Does not send raw file bytes to the UI** — File processing is server-side only
- **Does not display employee row values** — Only metadata (row count, column names) is shown
- **Does not allow progression on BLOCKED results** — The UI renders results; it does not provide a "proceed anyway" button
- **Does not auto-select a demo company** — User must explicitly click to initiate a scan

---

## Integration Points

| Component | Source |
|-----------|--------|
| Demo company cards | `executive-ui/src/data/demoCompanies.ts` |
| Real scan results | `POST /v1/tenants/{id}/upload/scan` |
| Demo scan results | `GET /v1/tenants/{id}/upload/demo/{company_id}` |
| Readiness config | `READINESS_CONFIG` in `DataUpload.tsx` |
| Governance disclaimer | `<GovernanceDisclaimer compact />` component |

---

## Future Wizard Steps (Post-Pilot)

The following steps are designed but not yet implemented (pending JWT auth and persistent storage):

1. **Step 4: Schema Mapping** — Map uploaded columns to theory constructs
2. **Step 5: Theory Activation** — Review which constructs were activated
3. **Step 6: Model Training** — Initiate supervised or exploration-mode analysis
4. **Step 7: Readiness Gate** — Final confirmation before live analysis

These are planned for the controlled Saudi pilot phase. The Phase 9 implementation covers Steps 1–3.
