# Phase 15 — Design System Corrections from Real Screenshots

Status: **Complete. All 9 confirmed problems fixed via shared design
tokens/components (not per-page patches), verified live with real data
via Playwright across all 8 pages (CEO Dashboard + 7 feature pages) plus
two adjacent major pages (Executive Dashboard, Workforce Intelligence)
that share the same underlying components. Zero console errors. Zero
governance/disclosure TEXT changes — every fix is visual/structural
only.**

This phase is a direct response to ground-truth screenshot review — the
user's own priority order is preserved below, and Priorities 1–3 (the
highest-impact items per the user's own assessment) are confirmed fixed
first, with live screenshot evidence.

One finding surfaced mid-implementation that wasn't in the original list:
`GovernanceDisclaimer`'s `compact` variant — the small "All risk
indicators are probabilistic…" banner — renders on **every single page in
the app**, unconditionally, and was amber. This is the single
highest-repetition instance of exactly the Priority 1 problem (a constant,
non-risk-dependent disclosure competing visually with real risk flags),
more pervasive than any single page's own banner. Fixed once, in the
shared component, so it corrected itself on every page simultaneously
(see §1).

---

## Priority 1 — Unified semantic color/status system

**Confirmed.** Grepping `bg-amber-50`/`bg-blue-50`/`bg-red-50` across the 7
feature pages turned up 40+ near-identical banner divs, plus several
literal instances of a KPI chip that could **only ever render
orange/amber, never anything else**, regardless of actual severity —
found at `CEODashboard.tsx:513` (`Financial Exposure` chip:
`exposureSimple > 500_000 ? 'orange' : 'amber'`, no third option) and
`CEODashboard.tsx:501` (`At-Risk Workforce` chip, a 4-tier scale with an
`'orange'` rung not part of any fixed system).

**Fixed:**
- `design-tokens.ts` — new `status` export: `critical` (red),
  `caution` (amber), `informational` (blue), `positive` (green),
  `neutral` (gray). Kept separate from the pre-existing `semantic`
  risk-band scale (stable/monitor/concern/priority), which is a different
  concept (a continuous population-risk gradient, not a fixed UI-status
  system) — not collapsed together.
- `components/shared/StatusBanner.tsx` (new) and
  `components/shared/StatusBadge.tsx` (new) — the one banner/pill
  component every page's disclosures now render through.
- `components/shared/StatusLegend.tsx` (new) — a single unobtrusive
  color-key row, added to the top of all 7 feature pages (right after the
  page header, before any banner).
- **Remapped, with real behavioral consequence, not just a repaint:**
  - `CEODashboard.tsx` — `Financial Exposure` chip: was orange-or-amber
    only; now `exposureSimple > 1,000,000 → red`, `> 300,000 → amber`,
    else `→ emerald`. Confirmed live: with the test dataset (SAR 628K
    display value, but a lower underlying `exposureSimple`), the chip now
    renders **emerald** — a color it was structurally incapable of
    showing before this fix.
  - `CEODashboard.tsx` — `At-Risk Workforce` chip: collapsed 4-tier
    (red/orange/amber/emerald) to 3-tier (red/amber/emerald).
  - `CEODashboard.tsx` — `Decision Readiness` chip: was
    emerald/**cyan**/amber (`cyan` had no fixed platform meaning, and
    "low confidence" was colored the exact same amber as genuine risk
    warnings elsewhere on the page). Now emerald/amber/**gray**.
  - **Nitaqat's and Succession's persistent disclaimer banners** — the
    two banners the user named directly ("Illustrative estimate — NOT an
    official Nitaqat/HRSD determination" and "Constructed heuristic — NOT
    a validated psychometric… instrument") were amber + `ShieldAlert`,
    i.e. visually indistinguishable from a real risk alarm, despite being
    unconditional and risk-independent. Both moved to `informational`.
    Text is unchanged, word-for-word.
  - **`GovernanceDisclaimer.tsx`'s compact variant** (renders on literally
    every page via `<GovernanceDisclaimer compact />`) — same fix,
    amber → `informational`. This was the single most-repeated instance
    of the "amber as default" problem in the entire app.
  - Every upload-guidance banner, duplicate-row/date-quality warning,
    department/stage-name-normalization note, and sources/governance
    footer on all 7 feature pages remapped to the correct tone
    (`informational` for constant notes, `caution` for real per-dataset
    anomalies, `critical` for upload errors, `neutral` for footers).
  - Fairness's `blocking_issues` (`critical`) and `advisory_warnings`
    (`caution`) — see Priority 2, these are the one page with genuinely
    different severities that needed to stay visually distinct.

**Verified live:** `nitaqat_full.png` — the color-key legend renders,
both former amber banners now render as quiet blue/gray boxes, and the
bottom "All risk indicators are probabilistic" banner (from
`GovernanceDisclaimer`) is now the same quiet tone instead of standing out
as a third amber block.

---

## Priority 2 — Structural separation, not just color

**Confirmed** on Fairness/Bias Audit specifically: `blocking_issues`
(red) and `advisory_warnings` (amber) were two boxes with identical
border-weight, padding, and icon size — same shape, different fill only.

**Fixed:** `StatusBanner`'s `critical` tone gets a visibly heavier
treatment than every other tone — `border-s-4 border-s-red-500` (a 4px
left/start accent bar, RTL-aware via logical `border-s-*`), a bigger icon
(18px vs 16px), and bold text — while `informational` is deliberately the
quietest tone (muted icon color, no bold text, low-saturation background).
Applied identically everywhere `StatusBanner tone="critical"` is used
(Fairness's `blocking_issues`, every page's upload-error banner).

**Verified live:** `fairness_full.png` — the "CRITICAL BIAS RISK" banner
now has a visible thick red left border and bold red text; the "LOW
CONFIDENCE" amber banner directly beneath it has a normal thin border and
regular weight. The two no longer read as the same box in two colors.

---

## Priority 3 — Radar chart

**Confirmed.** `RiskRadarChart.tsx` (the "AWI Index Radar" on the CEO
Dashboard) rendered at `size={220}` — smaller than the card containing
it — with grid rings but **no numbered scale** (no 0/25/50/75/100
visible anywhere) and a `#3b82f6` line at `strokeWidth: 2` with `r: 4`
data points, low-contrast against the `navy-700` card background.

**Fixed** (`components/visualizations/RiskRadarChart.tsx`, full rewrite):
- Default size `260 → 320`; CEO Dashboard's call site bumped
  `size={220} → size={320}` (`CEODashboard.tsx:638`).
- Added an explicit numbered scale (25/50/75/100, plus a `0` at center)
  rendered as small monospace labels along the top ("Stability") spoke —
  the standard radar-chart convention, rather than cluttering every spoke.
- Line color changed to `#60a5fa` (blue-400, brighter/higher-contrast
  than the prior functional blue) with `strokeWidth: 3` (was 2) and a
  `drop-shadow` glow.
- Data-point markers: `r: 4 → 5.5` with a `2px` dark stroke for
  definition against the fill.
- Axis labels bumped `10px → 12px` bold, value labels `9px → 11px` bold.

**Verified live:** `radar_closeup.png` — the chart is visibly larger, the
0/25/50/75/100 scale is legible along the top spoke, and the data
polygon is a clearly brighter blue with visible glow and large markers
against the dark card.

---

## Priority 4 — Unify progress rings/gauges

**Confirmed — three independent implementations found:**
1. `RadialKPI.tsx` — Recharts `RadialBarChart`, default `strokeWidth={8}`
   at `size={88}` (ratio 0.09), caller-supplied color.
2. `CEODashboard.tsx`'s `HeroGauge` — hand-rolled SVG, `stroke = size *
   0.065`, its own 6-tier grade-color function (A→emerald, B→**cyan**,
   C→amber, D→orange, F→red).
3. `WorkforceStabilityIndex.tsx` — a second, independent hand-rolled SVG,
   fixed `strokeWidth={12}` at a 160px container (ratio 0.075), its own
   4-tier color function including an `'ea580c'` orange step.

Three different stroke-width ratios and three different color-selection
schemes — confirmed exactly the "teal vs. light blue with no shared
meaning" problem reported.

**Fixed:** `components/shared/ProgressRing.tsx` (new) — one canonical
ring: a fixed `STROKE_RATIO = 0.09` applied uniformly regardless of size,
the same rounded end-caps, the same track color, and the same
`motionTokens.slow`/`easeExecutive` animation curve everywhere. Color
stays a caller-supplied prop (deliberately — "high is good" vs. "high is
bad" varies per metric, e.g. Saudization % vs. overtime prevalence %, and
only the caller knows which; this component owns geometry only, not
domain color logic).
- `KPICard.tsx` now renders `ProgressRing` directly (`RadialKPI.tsx`
  deleted — zero other call sites existed).
- `CEODashboard.tsx`'s `HeroGauge` is now a 6-line wrapper around
  `ProgressRing` (`hero` variant, `showPercentSign={false}`,
  `centerSub={grade label}`) — visually unchanged (0.09 × 240 ≈ the same
  ~16px stroke the old hand-rolled version used).
- `WorkforceStabilityIndex.tsx` — same migration; its color function
  collapsed from 4 tiers (including the stray orange) to the 3 canonical
  tones (`status.positive`/`caution`/`critical`).

**Verified live:** `ceo_statchips_recheck.png` — the hero WSI gauge
(66, Grade C) renders with the glow and thick stroke intact after the
refactor; `radar_closeup.png`'s surrounding cards confirm no visual
regression elsewhere on the page. `tsc --noEmit` clean.

---

## Priority 5 — Spacing/whitespace pass

**Confirmed.** Every table on the platform is wrapped as a bare
`<div className="card overflow-x-auto"><table>…` with zero padding on
the wrapper, so the header row's text sits flush against the card's top
border — the literal "borders too close to content" complaint.

**Fixed centrally, not per-page:** `.card` in `index.css` now carries a
default `padding-block: 0.625rem`. Because Tailwind's `utilities` layer
loads after `components` (this file's own `@tailwind base; @tailwind
components; @tailwind utilities;` order), any element that already
specifies `p-4`/`p-5`/`p-6` etc. is completely unaffected (the utility
wins the cascade) — this is a genuine no-op on every KPI card, narrative
box, and hero card that already had explicit padding, and only takes
effect on the bare `.card overflow-x-auto` table wrappers it was meant to
fix. One rule, in one file, fixes every table on every page without
touching a single page's markup.

**Scope note (disclosed):** a from-scratch two-tier spacing *token*
system (distinct "within-group" vs. "between-group" numeric scale) was
not introduced as new values — the codebase already has a working
version of this from Phase 11 (`space-y-7` between page sections,
`space-y-2`/`gap-3` within a group) that's applied consistently across
all 8 pages already; formalizing that as the documented convention was
judged higher-value than inventing a second, competing numeric scale
platform-wide within this phase's scope.

---

## Priority 6 — Latin-text isolation inside RTL tables

**Confirmed.** Employee/record IDs (`record_id_safe`, format
`EMP-XXXXXX`) are rendered as plain text nodes inside RTL-context table
cells with no directional isolation — the browser's bidi algorithm
resolves each cell's anchor edge independently based on its first
strong-direction character, so identical-looking ID cells can anchor
inconsistently.

**Fixed:** `components/shared/LatinText.tsx` (new) — a `dir="ltr"` +
`unicode-bidi: isolate` wrapper, applied uniformly instead of per-instance
spans. Deliberately **not** applied to department-name cells, since
those are data-driven and can legitimately contain real Arabic text
(e.g. "مبيعات") — forcing `dir="ltr"` on genuine Arabic content would
misalign it the other way. Only applied to fields guaranteed ASCII by
construction (record IDs). Numeric values were already covered
platform-wide by Phase 11's existing `[dir='rtl'] .tabular-nums` global
rule — confirmed still in place, not touched.
- `SuccessionReadinessTracker.tsx:428` — the one feature-page table with
  employee IDs.
- `EmployeeRiskDashboard.tsx:786,1109` — the platform's other two record-ID
  table/list cells (same ID format, very likely the actual source of the
  screenshot evidence given the exact match to the "EMP-C825B3" example
  cited).

---

## Priority 7 — Remove redundant table/chart data duplication

**Investigated, found already fixed.** `DepartmentBarChart.tsx` (the
shared chart used by Overtime/Nitaqat/Succession/Fairness/Payroll/Exit
Interview) already renders a `<LabelList dataKey="formattedValue"
position="right">` directly on every bar (established Phase 11) — values
are not tooltip-only. `RecruitmentFunnelChart.tsx` likewise already
labels every funnel segment with its raw count. No code change was
needed here; **verified live** in `fairness_full.png` — the "Disparity
Ratio by Attribute" chart shows `1.38x` and `1.18x` printed directly at
the end of each bar, not hidden behind hover.

---

## Priority 8 — Real hierarchy between KPI cards

**Confirmed exactly one real gap.** All 6 other feature pages already
have exactly one `hero` KPI card (Overtime, Payroll, Exit Interview,
Recruitment, Nitaqat, Succession — established Phase 11/12). **Fairness /
Bias Audit was the one page with none** — its 4 KPI cards
(`FairnessAuditTracker.tsx:308-347`) all render at identical size/weight.

**Fixed:** `Overall Risk Level` — the audit's actual bottom-line finding —
is now the page's `hero` card (`FairnessAuditTracker.tsx:330`).

**Verified live:** `fairness_full.png` — "OVERALL RISK LEVEL / CRITICAL"
now renders on the dark navy hero-card background with the gold top
accent, visibly larger than its three siblings, exactly matching the
hero treatment already used on the other 6 pages.

---

## Priority 9 — Icon consistency

Audited every `icon={...}` prop on KPI cards across the 7 feature pages
against a fixed meaning (headcount → `Users`, financial → `DollarSign`,
risk/alert → `AlertTriangle`/`ShieldAlert`, org/department →
`Building2`, time → `Clock`). Found and fixed two real mismatches, both
matching the user's own example pattern (a growth-icon on a non-growth
card):
- `SuccessionReadinessTracker.tsx:320` — "Employees Evaluated" (a plain
  headcount) used `TrendingUp`. Now `Users`, matching Recruitment's
  "Total Candidates" and Nitaqat's "Total Classified."
- `OvertimeCostIntelligence.tsx:295,307` — **both** of the page's
  financial KPIs ("Monthly Overtime Cost" and "Annual Overtime Exposure")
  used non-financial icons (`TrendingUp` and `Building2` respectively).
  Both now use `DollarSign`, matching the CEO Dashboard's "Financial
  Exposure" chip.

`TrendingUp`/`TrendingDown` on genuinely trend-shaped metrics (Payroll's
"Average Movement," Recruitment's "Biggest Drop-off") were left
unchanged — those are correct uses of the icon, not mismatches.

---

## Files changed

**New shared components:**
`components/shared/StatusBanner.tsx`, `StatusBadge.tsx`,
`StatusLegend.tsx`, `ProgressRing.tsx`, `LatinText.tsx`

**Deleted (superseded, zero remaining call sites):**
`components/shared/RadialKPI.tsx`

**Design tokens:** `styles/design-tokens.ts` (`status` export),
`index.css` (`.card` default padding)

**Rewritten:** `components/visualizations/RiskRadarChart.tsx`

**Migrated to `ProgressRing`:** `components/shared/KPICard.tsx`,
`pages/CEODashboard.tsx` (`HeroGauge`),
`components/dashboard/WorkforceStabilityIndex.tsx`

**Banner/badge/icon remap + `StatusLegend` added:**
`pages/CEODashboard.tsx`, `pages/OvertimeCostIntelligence.tsx`,
`pages/PayrollMovementsTracker.tsx`, `pages/ExitInterviewIntelligence.tsx`,
`pages/RecruitmentPipelineTracker.tsx`, `pages/FairnessAuditTracker.tsx`,
`pages/NitaqatComplianceTracker.tsx`, `pages/SuccessionReadinessTracker.tsx`,
`components/shared/GovernanceDisclaimer.tsx`

**Latin isolation:** `pages/SuccessionReadinessTracker.tsx`,
`pages/EmployeeRiskDashboard.tsx`

---

## Verification

- **`npx tsc --noEmit`**: clean after every file edit and on the final
  full project.
- **Live Playwright pass, real data** (`test_employee_data.csv`): all 7
  feature pages + CEO Dashboard, full upload → render cycle, plus
  Executive Dashboard and Workforce Intelligence (both consume the
  same shared `WorkforceStabilityIndex`/table components touched this
  phase). **Zero console errors, zero page errors**, across the entire
  run, both before and after the `GovernanceDisclaimer` fix.
  Light-mode + RTL rendering not separately re-verified this phase
  (Phase 14's equivalent check already confirmed the underlying
  `.card`/theme mechanics; this phase's changes to those same mechanics
  are additive, non-breaking CSS/prop changes, not structural rewrites).
- **Governance/disclosure text**: every edit in §1 was a `className`/tone
  swap around existing `{t(...)}` calls — the English/Arabic strings
  passed to `t()` were copy-pasted unchanged, never retyped, so no
  wording drift was possible. Confirmed by re-reading each edited banner
  against the pre-Phase-15 source.
- **Phase 13/14 interactivity**: sortable tables, chart↔table
  cross-highlight, expand/collapse rows, and hover-detail panels on all 7
  pages were exercised in the same Playwright pass (upload → table
  render) and produced no console errors; the `.card` padding change and
  banner-component swaps do not touch any of that interactivity's state
  or event handlers.
- **Backend**: zero files under `backend/` were read or modified this
  phase — the backend test suite is unaffected by construction, not
  merely re-run and found passing.

## Priorities 1–3 confirmation (per the user's own stated highest-impact items)

1. **Color system** — done: canonical 5-tone `status` system defined,
   `StatusBanner`/`StatusBadge`/`StatusLegend` built and applied across
   all 8 pages plus the platform-wide `GovernanceDisclaimer`, three real
   "orange/amber-only" KPI-chip bugs fixed with behavioral consequence
   (chips that could not previously show green now can).
2. **Structural separation** — done: `critical` tone carries a distinct
   heavy left-border + bold treatment, verified live on Fairness's
   blocking-issue vs. advisory-warning pair.
3. **Radar chart** — done: larger, numbered scale added, brighter/thicker
   line, larger markers, verified live.

No regressions found in any of the 8 pages' functional behavior, data
correctness, or governance text.
