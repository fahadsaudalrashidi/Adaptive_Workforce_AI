# AWI Design System — Phase 11

Deep-navy corporate-luxury visual system for the executive-ui frontend.
This document exists so a future session extends this system instead of
reinventing per-page conventions — the pattern established in
`NitaqatComplianceTracker.tsx` and `SuccessionReadinessTracker.tsx` (the
two most fully-realized pages) is the reference implementation.

## 1. Where things live

| Concern | File |
|---|---|
| Tailwind color/shadow/type/motion tokens | `tailwind.config.js` |
| JS-side token values (for Recharts, inline styles) | `src/styles/design-tokens.ts` |
| Global CSS component classes (`.card`, `.card-hero`, `.skeleton`, ...) | `src/index.css` |
| Count-up animation hook | `src/hooks/useCountUp.ts` |
| Shared visual components | `src/components/shared/*.tsx` |

Two token sources exist (Tailwind classes + `design-tokens.ts`) rather than
one, because Tailwind classes can't be read by a charting library — Recharts
needs real hex/rgba strings for `fill`/`stroke`/gradients. Keep them in
sync by hand; this codebase has no token-codegen tooling, and building one
would be a disproportionate build-pipeline change for a visual-layer phase.

## 2. Color system

**Why a new `navy` scale instead of reusing Tailwind's `slate`:** `slate` is
neutral gray — it doesn't read as "navy." The new `navy` scale
(`tailwind.config.js`) is more blue-saturated, used for the page background
(`navy-900`) and card elevation levels (`navy-700`/`navy-800`).

**Why `gold` is additive, not a blue replacement:** blue (`brand`/`#3b82f6`)
is the platform's existing functional/informational accent, used in
thousands of places across ~18,000 lines of pre-existing pages (buttons,
info banners, links, nav-active state). Ripping it out platform-wide would
be a full re-skin disproportionate to this phase's scope, and would risk
regressions in pages this phase didn't touch. Instead, `gold` (`#d4af37`
family) is a **new, restrained "premium marker"** layered on top: it marks
the one genuinely elevated moment on a page — a hero KPI card's top accent
bar, a Platinum-tier chart bar, a top-of-comparison chart bar. It should
stay rare. If most of a page is gold, the signal is gone.

**Semantic risk colors** (`risk.stable/monitor/concern/priority` in Tailwind,
`semantic.*` in `design-tokens.ts`) are unchanged from before this phase —
green/amber/orange/red, now centralized in `design-tokens.ts` so new chart
components use the exact same hex a badge already renders, instead of an
approximate one.

## 3. Elevation hierarchy

Three tiers, used deliberately — not every card should be the same weight:

1. **`.card-flat`** — secondary/dense surfaces: empty states, source-citation
   footers. Quiet border, no shadow.
2. **`.card`** — the default. Used everywhere already; upgraded in this
   phase with a subtle `shadow-elevation-1` and a hover transition, so
   every existing page gets a small, free upgrade without any per-page
   edit.
3. **`.card-hero`** — the page's single most important number. Deeper
   surface (`navy-700`), stronger shadow (`shadow-elevation-2`), and a gold
   top accent bar (`.card-hero-accent`). Apply to **one, maybe two** KPI
   cards per page — Saudization %, Overtime Prevalence, High Readiness
   count. Never apply it to everything; that defeats the hierarchy.

Add `.card-interactive` for hover lift (`-translate-y-0.5` + stronger
shadow) on any card the user might reasonably click or scan.

## 4. Typography

Named scale added to `tailwind.config.js` (`text-display` /
`text-headline` / `text-title` / `text-body` / `text-caption`) — additive,
not a replacement. Existing raw Tailwind sizes (`text-2xl`, `text-sm`,
etc.) remain valid and are still used throughout pre-existing pages;
introducing named sizes everywhere retroactively was out of scope. Use the
named scale for **new** components going forward (see `EmptyState.tsx`'s
`text-title`).

**Arabic**: Cairo (already loaded via Google Fonts in `index.html`) applies
automatically in RTL — `LanguageContext.tsx` already sets
`document.documentElement.dir`/`fontFamily` on language switch; this phase
didn't need to add that. What this phase DID add: `[dir='rtl']
.tabular-nums` forces LTR-isolated Western numerals even inside RTL flow
(`index.css`) — standard practice for financial/business data in Arabic UI
(Bloomberg Arabic, Qiwa, etc. all keep numerals Western; only prose
mirrors). Verified visually — see the Phase 11 report's RTL screenshots.

## 5. Motion

`transition-duration: fast (150ms) / base (250ms) / slow (400ms)` and a
shared `ease-executive` cubic-bezier, both in `tailwind.config.js`. Use
`duration-base ease-executive` for anything that should feel deliberate
(hover states, card transitions) rather than picking an arbitrary value.

`useCountUp()` (`src/hooks/useCountUp.ts`) animates a number from its
previous value to a new target on mount/update, respecting
`prefers-reduced-motion`. `KPICard`'s `animateValue` prop wires this in
automatically — it parses the numeric portion of an already-formatted
string value (`"61.4%"`, `"SAR 33K"`) and animates only the digits,
preserving whatever prefix/suffix/decimal-precision the caller passed.

## 6. Shared components (`src/components/shared/`)

- **`KPICard.tsx`** — extended (backward compatible) with `hero`,
  `animateValue`, `radialPct`/`radialColor`. See any of the 7 feature pages
  for usage.
- **`RadialKPI.tsx`** — standalone radial gauge (Recharts `RadialBarChart`),
  used by `KPICard` when `radialPct` is passed. Use directly only if you
  need a gauge outside a KPI card.
- **`DepartmentBarChart.tsx`** — horizontal, sorted-descending comparison
  bar chart. Generic despite the name (`{department, value, color,
  tooltipExtra}`) — reused for Nitaqat's Saudization-by-department,
  Succession's readiness-by-department, Overtime's prevalence-by-department,
  Fairness's disparity-by-*attribute*, Exit Interview's mentions-by-*theme*,
  and Payroll's movement-by-department. Always rendered **alongside**, not
  instead of, the existing data table — the chart is for at-a-glance
  comparison, the table remains for exact figures, screen readers, and
  print.
- **`RecruitmentFunnelChart.tsx`** — real funnel shape (Recharts
  `FunnelChart`) for stage-by-stage conversion data. Purpose-built for
  Recruitment Pipeline; not generic.
- **`EmptyState.tsx`** — the premium "data not detected" pattern (icon
  ring + requirement-chip grid), used wherever a module's
  `columns_detected: Record<string, boolean>` shape exists (Nitaqat,
  Succession, Recruitment). Fairness/Overtime/Payroll have a different,
  simpler unavailable-state shape (no `columns_detected` map) — they got a
  lighter visual polish (icon ring + `card-flat`) inline rather than
  forcing them into `EmptyState`'s prop shape.
- **`SkeletonAnalysis.tsx`** — shape-matched loading skeleton (KPI grid +
  narrative bar + table rows), replacing the old spinner-in-a-box pattern.
  Uses **fixed literal Tailwind classes**, not a dynamic `grid-cols-${n}` —
  Tailwind's JIT scanner only picks up class names that appear verbatim in
  source, so a template-literal class silently compiles to nothing. If you
  need a different KPI count, don't parameterize the grid — either accept
  gaps in a 4-column grid or add a second fixed variant.

## 7. What was deliberately NOT built, and why

**No period-over-period trend line for Payroll Movements**, despite the
brief asking for one. The `/api/local/payroll-movements` response only
returns an aggregate `org_avg_hike_pct` and a `n_periods_detected` count —
no per-period series exists in the API contract, even though the backend
computes movement internally per-period before aggregating. This phase's
brief explicitly prohibits backend/API changes ("visual layer
transformation only"). Building a "trend chart" from an aggregate would
mean either fabricating interpolated points (directly against this
session's entire honesty discipline) or silently changing an API contract
(explicitly out of scope). Payroll got the same department bar-chart
treatment as the other modules instead, using data that's genuinely
returned. If a future session wants a real trend line, the fix is a
backend addition (`period_series: [{period, avg_salary}]` or similar) —
that's a clean, separate piece of work.

## 8. Extending this system

- Reuse `DepartmentBarChart` for any new department/category comparison —
  don't build a new chart component for a shape it already handles.
- New hero numbers: use `KPICard`'s `hero`/`animateValue`/`radialPct`
  props, don't hand-roll a new elevated-card pattern.
- New "not detected" states: if the engine result has a
  `columns_detected: Record<string, boolean>` field, use `EmptyState`
  directly. If not, use the inline `card-flat` + `empty-state-icon-ring`
  pattern (see `OvertimeCostIntelligence.tsx`'s unavailable branch).
- Keep `gold` rare. One hero card, one chart's top bar. If a page has three
  gold elements, something's wrong.
