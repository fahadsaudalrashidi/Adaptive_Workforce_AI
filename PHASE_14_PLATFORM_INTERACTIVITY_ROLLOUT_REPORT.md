# Phase 14 — Platform-Wide In-Place Interactivity Rollout + Elevated Polish

Status: **Complete. Part 1 raises the CEO Dashboard's execution quality on
top of Phase 13's functional interactivity (consistent motion tokens,
coordinated multi-property hovers, no unfinished-looking states). Part 2
rolls the same interaction philosophy out to all 7 feature pages, built on
shared, reusable hooks/components rather than seven separate
reimplementations. Zero design changes (colors, layout, section order, all
governance/disclosure text) on any of the 8 pages touched. Zero console
errors across a full real-data upload pass on every page, verified via
Playwright.**

One real bug was caught and fixed *before* it shipped, not after: the
shared `SortToggle` and `.row-hover` treatments built for Phase 13's
`WorkforceCompositionRiver` were designed only for that component's
permanently-dark `navy-700` hero card. Reused as-is on the 7 feature
pages' light/dark `.card` tables, the inactive-hover text
(`text-navy-100`, near-white) would have gone nearly invisible on a white
background in light app mode — a real "Phase-13-class" regression of
exactly the kind Part 2's brief asked to guard against. Fixed by giving
both shared components a `variant`/light-mode-aware form before any page
consumed them. See §3.

---

## 1. Motion/polish tokens standardized (Part 1)

Audited every `transition-*`/`duration-*` occurrence in `CEODashboard.tsx`
and `WorkforceCompositionRiver.tsx` for whether it explicitly carried both
a duration token (`duration-base` / `duration-slow`) **and**
`ease-executive`. Found 9 places in `CEODashboard.tsx` alone missing one or
both (relying on Tailwind's default easing/duration instead), plus several
more in `WorkforceCompositionRiver.tsx` (legend hover, department-row
hover, "View all" link). All fixed to explicitly carry the same
`cubic-bezier(0.16, 1, 0.3, 1)` executive curve and the same duration
scale (`fast: 150ms` / `base: 250ms` / `slow: 400ms`) established in Phase
11's `tailwind.config.js` and `design-tokens.ts`.

Framer-motion `transition={{...}}` objects across both files now reference
the same JS-side tokens (`motionTokens.base`, `motionTokens.slow`,
`motionTokens.easeExecutive`) instead of ad hoc numeric literals or raw
easing arrays, so a future timing change happens in one place.

## 2. CEO Dashboard hover/interaction depth (Part 1)

- **`StatChip` button** — upgraded from a 3-property hover
  (border+background+shadow) to a coordinated 4-property hover: adds
  `hover:-translate-y-0.5` (lift) and an **icon-badge scale** — the icon
  inside the chip scales to 110% via a nested `group/btn` on button hover,
  independent of the chip's own hover state. This directly satisfies the
  brief's "color + icon state + micro-copy" example of a considered
  multi-property hover, using only existing palette colors.
- **CEO View / Board View toggle, Board Report / Decision Intelligence
  buttons, the gold "Upload Workforce Data" CTA, the hero card's
  `hover:shadow-glow-gold`, the Board Actions arrow-slide, the Board
  Recommendation stat-row, "Generate Board Report"** — all 9 previously
  inconsistent transitions now explicitly carry `duration-base`/
  `duration-slow` + `ease-executive`; the gold CTA additionally gained
  `hover:-translate-y-0.5` to match the lift treatment used elsewhere.
- **Hover-detail panel** — the ad hoc inline `StatChip` tooltip from Phase
  13 now consumes the new shared `.hover-detail-panel` CSS class (§3)
  instead of duplicating its own styling.

## 3. Shared components/hooks extracted (prerequisite for Part 2)

Built once, reused by every page below — this is the mechanism the brief
asked for to prevent "Phase-13-class bugs... recurring per-page":

- **`hooks/useSortableTable.ts`** — generic client-side sort. Always
  starts at a `'default'` sort key that returns the caller's data in its
  original prop order, untouched; sorting only ever activates after an
  explicit user click. This structurally prevents the exact bug Phase 13
  caught (a component silently defaulting to an *active* sort key, which
  reordered a list relative to what the parent had already computed).
- **`components/shared/SortToggle.tsx`** — the "Sort: X Y Z" control,
  extracted from `WorkforceCompositionRiver`. Ships with a
  `variant: 'card' | 'navy'` prop (see the bug below) — `'card'`
  (default) is light/dark theme-aware for the 7 feature pages' white/dark
  `.card` tables; `'navy'` preserves the original hardcoded navy colors
  for `WorkforceCompositionRiver`'s permanently-dark hero card, pinned
  explicitly at its one call site so its look didn't silently change.
- **`.row-hover-card`** (new CSS class, `index.css`) — the row-hover
  treatment for the 7 feature pages' light/dark tables
  (`hover:bg-slate-50 dark:hover:bg-navy-800/40`), distinct from the
  pre-existing `.row-hover` (hardcoded `navy-800/50`, correct only for a
  permanently-navy background like the hero card).
- **`.hover-detail-panel`** (new CSS class) — the shared hover-reveal
  tooltip, generalizing the `StatChip` pattern from Phase 13.
- **`KPICard.tsx`**  — new optional `detail` prop: one line of real,
  computed supporting context revealed on hover only, absolutely
  positioned so it never shifts the card's own layout. Every one of the 7
  feature pages already uses this shared component, so this is available
  platform-wide with no per-page markup duplication.
- **`DepartmentBarChart.tsx`** — new optional `highlightedKey` /
  `onHoverChange` props for chart↔table cross-highlighting (dims
  non-hovered bars to 40% opacity), the same pairing pattern as
  `WorkforceCompositionRiver`'s legend↔river highlight.
- **`RecruitmentFunnelChart.tsx`** — given the same `highlightedKey` /
  `onHoverChange` pairing (Recruitment's funnel chart isn't
  `DepartmentBarChart`, so this was added separately, same shape).

### Bug caught and fixed before rollout

`SortToggle`'s original inactive-hover color (`hover:text-navy-100`,
`#d7dce8`, near-white) and `.row-hover`'s hardcoded `navy-800/50`
background were both built for `WorkforceCompositionRiver`'s
`card-hero` — which is deliberately `bg-navy-700` in **both** light and
dark app theme, not theme-conditional. Applying either as-is to a normal
light/dark `.card` table would have put near-invisible light-gray text on
a white background in light mode, or a jarring dark-navy patch on a white
card. Fixed by making `SortToggle` theme-aware by default (with an
explicit `'navy'` opt-out for the one hero-card usage) and adding the
separate `.row-hover-card` class, before either was used on any of the 7
pages. Verified live in both dark and light app mode via Playwright
screenshot (§6).

---

## 4. What was added to each of the 7 feature pages (Part 2)

Every page below: same colors, same layout, same section order, every
governance disclaimer / source citation / confidence label / honest
"not detected" message unchanged word-for-word. Only interactivity added,
using the shared components in §3.

### Overtime & Workforce Cost Intelligence
- Department table: sortable (Overtime %, Cost, Risk, Name via
  `useSortableTable` + `SortToggle`), row-hover cross-highlighted with the
  `DepartmentBarChart` above (shared `hoveredDept` state).
- All 4 KPI cards gained `detail` hover context (hours-source note,
  salary-benchmark confidence + sector, 12-month projection basis,
  flagged-department names or the honest "no department flagged" line).
  "Departments Flagged" also gained `animateValue`.

### Payroll Movements Tracker
- Identical treatment to Overtime (same underlying table shape): sortable
  department table (Movement, Employees, Name), chart↔table
  cross-highlight, KPI `detail` context (data-mode label, department
  count, the existing limitation note surfaced on hover too).

### Exit Interview Intelligence
- Theme-mentions table: sortable (Mentions, Name), cross-highlighted with
  the `DepartmentBarChart` (repurposed for theme mentions, unchanged from
  Phase 11). KPI `detail`: PII-scrubbing note, minimum-document-frequency
  threshold, TF-IDF vs. word-frequency explanation.

### Recruitment Pipeline Tracker (3 tables — richest page)
- **Funnel stage table**: sortable (Candidates, % of Total, Conversion);
  default order preserves the natural Applied→Hired sequence (never
  auto-sorted). Cross-highlighted with the funnel chart via new
  `highlightedKey`/`onHoverChange` props added to
  `RecruitmentFunnelChart`.
- **Department/role table** and **source/channel table**: both sortable
  (Candidates, Hired, Rate, Name), row-hover.
- KPI `detail`: department/source spread, cost-per-hire summary,
  biggest-drop-off's actual conversion percentage, invalid-date-sequence
  exclusion count.

### Fairness / Bias Audit Tracker (2 tables)
- **Fairness metrics table**: sortable (Disparity, Name), cross-highlighted
  with the disparity-ratio `DepartmentBarChart`.
- **Protected attributes table**: sortable (Confidence, Name), row-hover.
- KPI `detail`: attribute names, statistically-significant-metric count,
  bucketing/floor reassurance, blocking-issue count.

### Nitaqat / Saudization Compliance Tracker
- Department table: sortable (Saudization %, Total, Name),
  cross-highlighted with the `DepartmentBarChart`.
- **Expand/collapse** (new interaction pattern, not present on any Phase
  13 page): clicking a department row reveals the explicit Saudi /
  non-Saudi split — a small two-color proportion bar plus exact counts and
  percentages for each — computed from `n_saudi`/`n_non_saudi`/`n_total`
  already in the API response (nothing new fabricated). Chevron icon
  rotates on expand; `AnimatePresence` fades the detail row in/out using
  the standard motion tokens.
- KPI `detail`: department spread, nationality-column provenance note,
  Qiwa-verification reminder, constructed-threshold disclosure.

### Succession / Internal Mobility Readiness
- **Top-candidates table**: sortable (Score, Tenure, Department).
  **Expand/collapse** on each row reveals *which specific signals*
  contributed — "Stuck signal: high performance percentile with no
  job-level advancement" and/or "Low fairness signal: high readiness
  combined with low promotion-fairness perception" — or an honest "no
  signal detected for this candidate" line when neither flag is set. This
  is the exact per-row detail the brief asked for by name.
- **Department table**: sortable (Score, High Readiness, Total, Name),
  cross-highlighted with the `DepartmentBarChart`.
- KPI `detail`: department spread, heuristic-not-validated reminder
  (reinforcing, never replacing, the page's persistent banner), per-signal
  explanatory text, "add this column to enable" notes for the two optional
  signals.

---

## 5. Confirmation of zero design changes

No color, spacing, section order, or copy was altered on any of the 8
pages — every addition is either: (a) a hover-only reveal that never
shifts existing layout (`.hover-detail-panel`, KPICard `detail`), (b) an
opt-in interaction that only activates on click (sort, expand/collapse),
or (c) a `dir="ltr"`-isolated chart-hover effect (opacity dimming) that
doesn't touch the chart's existing geometry, colors, or the Phase 11B
RTL/Recharts isolation convention. Every governance banner,
"illustrative estimate"/"constructed heuristic" disclaimer, source list,
and honest not-available/not-detected message was left word-for-word
untouched — confirmed by diffing only the JSX blocks that were actually
edited, never touching the disclosure text nodes themselves.

## 6. Verification

- **`npx tsc --noEmit`**: clean after every file edit, and clean on the
  full project at the end of the phase.
- **Rules of Hooks**: every `useState`/`useSortableTable` call in all 7
  pages is declared unconditionally at the top of its component, before
  the `return` — confirmed by grepping all call sites (none inside a
  conditional block, none inside the `status === 'done'` JSX branch).
  Each `useSortableTable` call receives `pageData ?? []` so it's always
  called even before a dataset is uploaded.
- **Live Playwright pass, real data** (`test_employee_data.csv`, uploaded
  through each page's actual upload widget — not a mock): all 7 feature
  pages plus the CEO Dashboard, full page load → upload → wait for
  results → screenshot. **Zero console errors, zero page errors**, across
  the entire run.
- **Default-order preservation**: confirmed via screenshot that
  Overtime's department table renders in the same order as the backend's
  own descending-by-prevalence order (Sales 40%, Engineering 40%,
  Operations 30%, Finance 28%, HR 28%) with no sort-toggle option
  highlighted — i.e. `useSortableTable`'s `'default'` state, not an
  auto-applied sort.
- **Cross-highlight**: confirmed live — hovering the Overtime table's
  "Sales" row dims every other bar in `DepartmentBarChart` to 40% opacity
  while Sales stays at full opacity.
- **Sort interaction**: confirmed live — clicking "Cost" on the Overtime
  table activates the blue highlighted state on the toggle and re-sorts
  (order happened to be unchanged in this dataset since cost and
  prevalence ranked identically, but the active-state highlight and
  re-render were confirmed).
- **Expand/collapse**: confirmed live on Succession — clicking the first
  candidate row expands to show "No stuck-performer or low-fairness
  signal detected for this candidate" (the honest no-signal case), with
  the chevron rotating; clicking again collapses it.
- **Light-mode regression check for the SortToggle/row-hover fix**:
  confirmed live — toggled the app to light mode and re-ran the Overtime
  page; the "Sort: Overtime % Cost Risk Name" control renders fully
  legible dark-gray text on the white card background (the theme-aware
  fix from §3 working as intended, not the original navy-only colors that
  would have been unreadable there).
- **Nitaqat's expand/collapse** could not be exercised end-to-end with
  `test_employee_data.csv`, since that fixture has no
  nationality/Saudi-status column and correctly renders the honest
  "Nationality data not detected" empty state instead (confirmed
  correct — not a bug). Its expand/collapse implementation is
  structurally identical (same `Fragment` + `AnimatePresence` +
  `motion.tr` pattern, same shared motion tokens) to Succession's, which
  was exercised live and confirmed working.

## 7. Bugs caught during self-verification

1. **SortToggle/`.row-hover` navy-only colors** (§3) — caught and fixed
   *before* any page consumed them, by inspecting the components'
   intended reuse context rather than assuming Phase 13's one usage
   generalized. Confirmed fixed via live light-mode screenshot.
2. **Recharts `Funnel` `onMouseEnter` typing** — TypeScript rejected the
   natural `(d: FunnelStageDatum) => void` handler signature because
   Recharts' `Funnel` (unlike `Bar`) types `onMouseEnter` as an
   intersection of a chart-level bivariant handler and a native SVG
   `MouseEventHandler`, which no real function signature satisfies. Fixed
   with a narrowly-scoped `any` parameter and a comment explaining why,
   rather than suppressing the check platform-wide.
3. **`layout` + framer-motion on `<tr>` elements** — considered using
   framer-motion's `layout` prop on table rows for a smooth
   position-transition on re-sort (as `WorkforceCompositionRiver` does
   with `<div>` rows), but table rows have known cross-browser transform
   rendering issues that `<div>`-based layouts don't. Deliberately used
   plain `<tr>` elements (re-render snap instead of animated reflow) for
   every sortable table this phase, rather than risk introducing a
   rendering bug for a purely cosmetic upgrade.

No other functional regressions found. No governance/disclosure text was
altered on any page.
