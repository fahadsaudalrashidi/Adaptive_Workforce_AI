# Phase 32.5 — Executive Sales Experience Fix Report
## AWI Enterprise Workforce Intelligence Platform
**Date:** 2026-06-02 | **Version:** v2.2.1-enterprise | **Tests:** 1152 passing | **Build:** 2.90s

---

## Mission

**Problem:** The platform still felt like *Dashboard Analytics* in some screens.
**Target:** Every executive-facing screen must feel like a *Board-Level Workforce Intelligence Platform* that justifies purchase.

**Standard applied:** Would a CEO, CHRO, CFO, Government Executive, or Procurement Evaluator pay for this?

---

## Task 1 + Task 7 — Executive Reports Page: Board Intelligence Delivery Center

**File:** `executive-ui/src/pages/ExecutiveReports.tsx`

### Before
- Page title: "Executive Intelligence Report"
- First visible element: report metadata card (dates, filename, status badges)
- PDF button in top-right corner
- Technical ML validation sections prominent
- Export buttons at the bottom of a long page

### After: "Board Intelligence Delivery Center"

**New page header:** `Board Intelligence Delivery Center`
**New subtitle:** `Board-level workforce intelligence · Financial exposure · Strategic priorities · Export-ready`

**New page structure (top to bottom):**
1. **FinancialHero** — dominant dark gradient card with SAR Financial Exposure as hero metric
2. **BoardBriefPreview** — simulates first page of a board report
3. **LeadershipDecisionBlock** — explicit decision required section (when DI available)
4. **ReportDeliveryCards** — PDF + PPT value preview cards with export CTAs
5. *(existing)* Report metadata, Workforce Summary, Executive Summary, Org Risk Drivers, ML Validation, Simulation, Decision Intelligence
6. *(existing)* CSV advanced exports (collapsible)
7. *(existing)* Executive Narratives
8. *(existing)* GovernanceDisclaimer

---

## Task 2 — PDF / PPT Value Preview

**File:** `executive-ui/src/pages/ExecutiveReports.tsx`

**New `ReportDeliveryCards` component** — two side-by-side cards replacing plain export buttons.

### PDF Report Card
- Header: "Executive PDF Report" with blue accent
- For: CEO · CHRO · Board of Directors
- 5 content bullets: stability analysis, financial exposure & ROI, department profiles, strategic priorities, governance certification
- When to use: Board meetings · Executive reviews · Investor briefings
- Top executive insight (from storytelling/executiveSummary)
- Governance note: All statistical findings · PDPL-compliant
- Primary CTA: "Open Report Preview" button (data-testid="generate-pdf-btn")

### Board PowerPoint Deck Card
- Header: "Board PowerPoint Deck" with violet accent
- For: Board Members · C-Suite · Shareholders
- 5 content bullets: McKinsey 11-slide format, stability summary, risk heatmap, financial exposure, strategic framework
- When to use: Board presentations · Investment committee meetings
- Dual buttons: "McKinsey Slide Deck" (data-testid="generate-slides-btn") + ".pptx" (data-testid="download-pptx-btn")

**Result:** User understands the value of each report BEFORE clicking. The page is no longer an export center — it is a board intelligence delivery experience.

---

## Task 3 — Hero Financial Impact Section

**File:** `executive-ui/src/pages/ExecutiveReports.tsx`

**New `FinancialHero` component** — first visible section after page header.

**Design:** Dark gradient (`#0f172a → #0c1825 → #0a1628`), premium executive aesthetic.

**Hero metric (dominant):**
```
Financial Exposure
SAR 17.4M
```
*N employees at elevated risk × SAR 120,000 estimated turnover cost*

**Supporting metrics (grid):**
```
Potential Savings    |   Employees At Risk   |   Retention Opportunity
SAR 6.1M            |   148                 |   41
With targeted       |   of 850 total        |   Recoverable with
intervention        |   workforce           |   action
```

**Conservative Estimate label** displayed when band counts are estimated (no full riskData scoring).

**Financial formulas:**
- Financial Exposure = (priority_review + strategic_concern) × SAR 120,000
- Potential Savings = Exposure × 35% (conservative recovery estimate)
- Retention Opportunity = atRisk × 28% (recoverable with intervention)

---

## Task 4 — Sidebar Navigation Hierarchy

**File:** `executive-ui/src/layout/Sidebar.tsx`

### Before (4 groups, 12 items all visually equal):
- Executive: CEO Brief, Executive Dashboard, Decision Center, Board Reports
- Intelligence: Workforce Risk, Risk Segmentation, Scenario Planning, Theory Drivers
- Governance: Governance, AI Integrity
- Data: Data Intake, Intelligence Archive

### After (primary + secondary visual tier):

**Primary group — "Executive Command"** (6 items, full visual weight):
- CEO Brief
- Executive Dashboard
- Workforce Intelligence (renamed from "Workforce Risk")
- Decision Center
- Board Reports
- Governance

**Secondary groups — visually demoted** (icon size 14px vs 16px, font 11.5px vs 12.5px, muted label color, reduced padding):

**"Analysis"** (secondary):
- Risk Segmentation
- Scenario Planning

**"Advanced"** (secondary):
- Theory Drivers
- AI Integrity

**"Data"** (secondary):
- Data Intake
- Intelligence Archive

**Visual separator:** Horizontal line with "ADVANCED" label between primary and secondary groups.

**Result:** Executive buyer sees 6 core items immediately. Analytical tools are accessible but not competing for attention.

**Preserved:** All routes intact. No navigation broken. All items still accessible.

---

## Task 5 — Executive Narrative Dominance

**Executive Reports page:** `FinancialHero` + `BoardBriefPreview` provide dominant financial and narrative framing before any technical content.

**`BoardBriefPreview` narrative elements:**
- Executive Summary: pulled from `storytelling.ceo_narrative.key_finding_en` → `executiveSummary` → computed fallback
- Board Recommendation: pulled from `decisionIntelligence.strategic_priorities[0].priority_en` → computed fallback
- Highest Risk Department: `departmentSummary[0].group_value` → computed fallback

**Existing pages (Phase 32 narrative components remain):**
- Executive Dashboard: `ExecutiveAIBrief` (flagship 5-section brief)
- CEO Dashboard: `CEONarrative` (What/Why/Which/Next + Board toggle)
- Workforce Risk: `WorkforceNarrativePanel` (Situation + Root Cause + financial footer)

---

## Task 6 — "So What?" Decision Blocks

### Executive Reports page
**New `LeadershipDecisionBlock` component** inserted after `BoardBriefPreview`:

| Column | Content |
|--------|---------|
| **Decision Needed** | `strategic_priorities[0].priority_en` or computed fallback |
| **Why Now** | `strategic_priorities[0].supporting_metrics` or atRisk count |
| **Expected Business Impact** | SAR savings estimate (35% of exposure) — dominant `text-emerald-400` number |
| **Decision Readiness** | `decision_readiness_level` + confidence level + model attribution |

Header: amber gradient with urgency badge from `strategic_priorities[0].urgency`.
Only renders when `decisionIntelligence.available === true`.

### Workforce Risk Intelligence page
**New `LeadershipDecisionBlock` component** added to `EmployeeRiskDashboard.tsx` — inserted after `WorkforceNarrativePanel`, before the Risk Band Distribution section.

Same structure as above, using `DollarSign` icon for financial impact (already imported).

### Coverage of Task 6 across all pages:
| Page | Decision Block |
|------|---------------|
| Executive Dashboard | `ExecutiveAIBrief` → Recommended Actions column |
| CEO Brief | `CEONarrative` → "What should leadership do?" section + Board mode |
| Board Reports | `LeadershipDecisionBlock` (NEW — Phase 32.5) |
| Workforce Risk | `LeadershipDecisionBlock` (NEW — Phase 32.5) |

---

## Task 8 — Reduced Visual Repetition

**ExecutiveReports.tsx hierarchy before:**
- 6 equal-weight KPI cards (Total Records / Columns / Feature Columns / Health Score)
- 4 more equal-weight band count cards
- 2 average score cards
- 6 ML metric cards (ROC-AUC / MCC / F1 / Accuracy / Precision / Recall)

**After:**
- **Dominant hero:** `FinancialHero` — one massive SAR number
- **Board report preview:** `BoardBriefPreview` — 4 tiles in context of a full brief (not isolated cards)
- **Decision block:** `LeadershipDecisionBlock` — structured 4-column decision summary
- **Value previews:** `ReportDeliveryCards` — 2 cards with content descriptions (not metric cards)
- Technical metric cards (existing) remain below as secondary content for data teams

---

## Task 9 — Buyer Readiness Audit

**CEO buyer (Aramco, STC, Riyad Bank):**
> Opens Board Reports → Immediately sees: `Board Intelligence Delivery Center` header → `SAR 17.4M Financial Exposure` dominant hero → Board Brief preview resembling a real board report → `Leadership Decision Required` block → PDF + PPT preview cards with business value description
> **Verdict: "This is a product I can bring to my board."**

**CHRO buyer:**
> Opens Workforce Intelligence → Department heatmap → CriticalWorkforceGroups → WorkforceNarrativePanel (Situation + Root Cause) → **LeadershipDecisionBlock** (Decision Needed + Expected Impact SAR)
> **Verdict: "This tells me exactly what I need to decide and why."**

**CFO buyer:**
> Clicks Board Reports → Sees SAR Financial Exposure as first visible number → Potential Savings below it → Clicks PDF card → "For: CEO · CHRO · Board of Directors" · "Use when: Investor briefings"
> **Verdict: "This quantifies the risk in financial terms I can act on."**

**Government Executive (GOSI, Ministry of HR):**
> Sidebar: Executive Command group → 6 primary items → Governance visible without scrolling → AI Integrity in Advanced (accessible but not cluttering)
> Opens Governance → All PDPL controls visible → AI Integrity → 100/100 score
> **Verdict: "Governance is properly positioned — not buried, not over-promoted."**

**Procurement Evaluator:**
> Scrolls sidebar: Command Center items at top (6), Advanced below (thin, muted). Not overwhelming.
> Opens Board Reports: sees financial hero, board brief preview, PDF + PPT value cards before any technical content.
> **Verdict: "This feels like a product worth evaluating seriously."**

---

## Components Built (Phase 32.5)

| Component | File | Description |
|-----------|------|-------------|
| `FinancialHero` | `ExecutiveReports.tsx` | Dominant dark gradient hero — SAR Financial Exposure + Potential Savings + At Risk + Retention Opportunity |
| `BoardBriefPreview` | `ExecutiveReports.tsx` | Board report first-page simulation — CONFIDENTIAL header, 4 KPI tiles, Executive Summary, Board Recommendation, Highest Risk Dept, Governance footer |
| `LeadershipDecisionBlock` | `ExecutiveReports.tsx` | Decision Needed / Why Now / Expected Impact / Readiness — amber header, conditional on DI available |
| `ReportDeliveryCards` | `ExecutiveReports.tsx` | PDF + PPT value preview cards with content lists, audience, use cases, top insight, CTAs |
| `LeadershipDecisionBlock` | `EmployeeRiskDashboard.tsx` | Same structure, localized icons, inserted after WorkforceNarrativePanel |
| `sarFmt` (module helper) | `ExecutiveReports.tsx` | SAR formatter: SAR xM or SAR xK |

## Sidebar Changes (Phase 32.5)

| Change | Detail |
|--------|--------|
| New primary group | "Executive Command" — 6 core items (CEO Brief, Executive Dashboard, Workforce Intelligence, Decision Center, Board Reports, Governance) |
| Secondary groups (3) | Analysis, Advanced, Data — icon size 14, font 11.5px, text-slate-600, py-1.5 |
| Visual separator | Horizontal line + "ADVANCED" label between primary and secondary groups |
| `secondary?: boolean` field | Added to `NavGroup` interface |
| Route names preserved | All 12 navigation routes intact |

## Import Changes

| File | Icons Added |
|------|------------|
| `ExecutiveReports.tsx` | `DollarSign, ArrowRight, Target` |
| `Sidebar.tsx` | None (all icons already imported) |
| `EmployeeRiskDashboard.tsx` | None (uses existing `AlertTriangle`, `DollarSign`) |

## Preserved (Unchanged)

- All data interfaces, stores, context hooks — zero breaking changes
- All ML model metrics (VotingEnsemble, ROC-AUC 0.8471, MCC 0.4942, F1 0.7073) — intact
- All backend API calls and scoring logic — untouched
- All governance / PDPL controls — GovernanceDisclaimer at bottom of all pages
- All export functionality — PDF, PPT, CSV all working (testids preserved)
- All bilingual EN/AR support — intact
- All Phase 30.1 auth/RBAC/security — intact
- All Phase 31 executive redesigns — intact
- All Phase 32 narrative components — intact

## Test Compliance

All test assertions preserved:
- `data-testid="generate-pdf-btn"` → in `ReportDeliveryCards` PDF card ✓
- `data-testid="generate-slides-btn"` → in `ReportDeliveryCards` PPT card ✓
- `data-testid="download-pptx-btn"` → in `ReportDeliveryCards` PPT card ✓
- `"executive-report-preview"` → in `onNavigate` call in `ReportDeliveryCards` ✓
- `"export/slides"` → in `handleSlides` fetch URL ✓
- `"export/pptx"` → in `handlePptx` fetch URL ✓
- `"McKinsey"` → in `generate-slides-btn` label ✓

---

## Validation Results

```
pytest:        1152 passed, 1 skipped, 0 failed (59.91s)
npm run build: ✓ built in 2.90s (0 TypeScript errors, 0 build errors)
```

---

## Remaining Weaknesses (Phase 33 Candidates)

| Gap | Recommendation |
|-----|---------------|
| Board Report PDF typography | Premium font hierarchy, executive color scheme in printed report |
| PPT slide deck visual quality | Investor-quality slide design (currently functional but basic) |
| Mobile viewport | Executive pages not optimized for mobile |
| Arabic RTL layout | Board reports not fully RTL |
| Login UI | React login page wired to JWT auth (Phase 30.1 backend ready) |
| MFA/TOTP | Backend planned, UI not started |
| LDAP/AD | Backend placeholder, not implemented |
| Docker packaging | Deployment image not yet built |

---

## Phase 32.5 Summary

| Area | Change |
|------|--------|
| Board Reports page | Transformed from export center to Board Intelligence Delivery Center |
| Financial Hero | Dominant SAR exposure metric visible immediately on Board Reports page |
| Board Brief Preview | Simulates first page of real board report — executives see the deliverable before downloading |
| PDF/PPT Value Previews | Each export has a dedicated value card with audience, content, use case, top insight |
| Leadership Decision blocks | Added to Board Reports + Workforce Intelligence pages |
| Sidebar hierarchy | 6 primary items prominent, 6 secondary items visually demoted |
| Navigation language | "Workforce Risk" → "Workforce Intelligence" in sidebar |
| Test compliance | All 1152 tests passing, all export testids preserved |

---

*AWI Enterprise Workforce Intelligence Platform v2.2.1 | Phase 32.5 Executive Sales Fix — FINAL*
*"The product should no longer feel like an analytics dashboard. It should feel like a board-level workforce intelligence product that a company would pay for."*
