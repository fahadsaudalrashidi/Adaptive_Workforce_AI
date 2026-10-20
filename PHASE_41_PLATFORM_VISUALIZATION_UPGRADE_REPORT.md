# Phase 41 — Platform-Wide Data Visualization Upgrade

Real charts (matched to data shape, not defaulted to one style) and purposeful motion for every surviving module, built entirely on the Phase 15 design system (`critical`/`caution`/`informational`/`positive`/`neutral` tokens, `StatusBadge`/`StatusBanner`/`StatusLegend`, `ProgressRing`, `KPICard`) — no new color palette, no new component conventions invented from scratch.

## Foundations verified before writing any code

Before touching a single page, a research pass confirmed (not assumed) what already existed:

- **Recharts** is installed and already powers two real, reusable, cross-highlight-capable chart components: `DepartmentBarChart.tsx` (horizontal ranked bar, value printed at bar end) and `RecruitmentFunnelChart.tsx` (real funnel). Both claims in the task brief — Overtime Cost's ranked bar and Recruitment's funnel — checked out exactly as described.
- `StatusBadge`/`StatusBanner`/`StatusLegend`/`ProgressRing` all exist, are non-trivial, and are wired into the majority of the platform's pages.
- `useCountUp` (count-up animation), `useSortableTable`, and chart↔table cross-highlight (`highlightedKey`/`onHoverChange`) all exist and are exercised on real pages already.
- **Only 7 of 24 routed pages had any chart at all** going into this phase (6 using `DepartmentBarChart`, 1 the funnel). The other 17 were KPI-card/table/form-only and needed genuinely new chart work — not just wiring up something latent.
- **No time-series (line/area) or proportional-composition (donut/stacked) chart component existed anywhere in the live codebase.** Two new shared components were built from scratch to cover those data shapes: `TrendChart.tsx` and `CompositionChart.tsx`, both in `src/components/shared/` alongside the existing two, using the same recharts/theme/`categorical`-palette conventions, the same `dir="ltr"` isolation fix, and (for `CompositionChart`) the same `highlightedKey`/`onHoverChange` cross-highlight pairing.
- `DepartmentBarChart` gained one new prop, `sortByValue` (default `true`, fully backward compatible) — for the ordered-stage data (AR/AP aging buckets, contract/Iqama urgency tiers) where the category *sequence* is the signal, not the value ranking.

## 1. Chart-type decision per module

### Already had a chart (verified correct, unchanged)

| Module | Chart | Why |
|---|---|---|
| Overtime Cost Intelligence | `DepartmentBarChart` | Ranked department comparison — the canonical Phase 11 pattern this phase replicated everywhere else. |
| Exit Interview Intelligence | `DepartmentBarChart` | Ranked theme-mention comparison. |
| Fairness / Bias Audit | `DepartmentBarChart` | Ranked disparity comparison. |
| Nitaqat / Saudization | `DepartmentBarChart` | Ranked Saudization comparison. |
| Succession Readiness | `DepartmentBarChart` | Ranked readiness comparison. |
| Recruitment Pipeline | `RecruitmentFunnelChart` | Genuine narrowing funnel shape. |
| **Payroll Movements** | `DepartmentBarChart` only — **deliberately no trend chart added** | The task brief named this as a time-series example. Ground-truth check of `PayrollMovementsTracker.tsx`'s actual API model (`PayrollMovements` interface) found no period-indexed array is ever returned by the backend — even in `data_mode: 'longitudinal'`, the response carries only an aggregate `avg_hike_pct` per department and an `n_periods_detected` *count*, never a per-period series. Adding a line chart here would mean inventing points the API doesn't provide — the same governance violation this codebase has refused everywhere else. The existing ranked bar remains the only real, honest chart this page's actual data supports. |

### New chart work this phase (11 pages)

| Module | Tab | Chart added | Data shape / why |
|---|---|---|---|
| **Financial Intelligence** | Revenue | `CompositionChart` (donut) | `revenue_by_category[]` — proportional breakdown. |
| | Expense | `CompositionChart` + `DepartmentBarChart` | `expense_by_category[]` (proportional) + `expense_by_department[]` (ranked). |
| | P&L | `TrendChart` (multi-series area) | `period_figures[]` — real period-indexed revenue/expense/net, only rendered when `has_period_trend`. |
| | Cash Flow | `TrendChart` (multi-series area) | Same `period_figures[]`, inflow/outflow/net framing, only when `cash_flow_available`. |
| | Ratios | `ProgressRing` (via `KPICard.radialPct`) | Top expense/revenue concentration are already percentages — the exact "score/percentage headline number" case the brief calls out; previously bare numbers. |
| **Accounting Intelligence** | General Ledger | `DepartmentBarChart` | Ranked net position by account. |
| | Balance Sheet | `CompositionChart` | Assets/Liabilities/Equity — a textbook 3-part composition. |
| | AR/AP Aging | `DepartmentBarChart` (`sortByValue=false`) | Ordered aging buckets (current → 90+) — the staged visual the brief explicitly suggested, using bucket *order* not value rank. |
| **Inventory Intelligence** | ABC Analysis | `CompositionChart` | `tier_value_pct` (A/B/C) — proportional value concentration. |
| | Stock Aging | `DepartmentBarChart` | 4-tier (active/watch/slow-moving/dead-stock) ranked counts. |
| **Procurement Intelligence** | Supplier Spend | `DepartmentBarChart` | Ranked spend by supplier. |
| | Price Trend | `TrendChart` (per item) | `period_variances[]` per supplier-item pair — real period-indexed price series. |
| | Delivery | `DepartmentBarChart` | Ranked on-time % by supplier. |
| | Supplier Score | `DepartmentBarChart` | Ranked composite score. |
| **Logistics Intelligence** | Status Overview | `CompositionChart` | `status_counts[]` — a distribution that sums to the shipment total. |
| | Delivery Time | `ProgressRing` (`radialPct`) | On-time % headline number, was bare. |
| | Shipping Cost | `DepartmentBarChart` + `TrendChart` | Ranked cost by carrier + real monthly cost `period_variances[]`. |
| | Carrier & Route | `DepartmentBarChart` | Ranked carrier composite score. |
| | Returns | `DepartmentBarChart` | Ranked return-theme mentions (mirrors Exit Interview's established convention exactly). |
| **Operations Intelligence** | Productivity | `DepartmentBarChart` | Ranked productivity by unit. |
| | Utilization | `DepartmentBarChart` | Ranked utilization % by unit. |
| | Downtime | `DepartmentBarChart` ×2 | Ranked downtime hours by unit + ranked cause-theme mentions. |
| | Quality | `DepartmentBarChart` + `TrendChart` | Ranked defect rate by unit + real defect-rate `period_variances[]` — the brief's named "Operations quality trends" example. |
| | Cost per Unit | `DepartmentBarChart` | Ranked cost/unit. |
| **Pay Equity** | — | `DepartmentBarChart` | Pay-gap % ranked by cohort, colored by statistical significance. |
| **Contract Expiry & Renewal** | — | `DepartmentBarChart` ×2 (`sortByValue=false`) | Contract and Iqama urgency-tier counts, ordered (overdue → monitored 90+) — same staged pattern as AR/AP aging. |
| **Job Pattern Grouping** | — | `DepartmentBarChart` | Ranked employee count by job pattern. |
| **Payroll Budget Planner** | — | `DepartmentBarChart` | Ranked payroll cost variance by department (only rendered once a plan is entered — nothing to rank before that). |
| **GOSI Contribution Calculator** | — | `DepartmentBarChart` | Ranked total contribution by department. |

## 2. Modules and tabs judged chart-inappropriate (and why)

Per the brief's own carve-out — never forcing a chart where the underlying data doesn't support one:

- **Enterprise Overview** — pure navigation hub, no analytical data to visualize by design.
- **Trust Panel (AI Integrity)** — governance/audit status content, not a metric series.
- **AI Business Analyst** — a conversational Q&A interface; there's no aggregate to chart.
- **HR Letter Generator** — a per-document generator; output is a letter, not a metric.
- **Saudi Labor Law Calculators** — three independent single-scenario calculators (Gratuity/WPS/Leave); each run produces one result, not a comparable category array.
- **Zakat Base Estimator** — single manual balance-sheet entry; no array of comparable items exists to chart.
- **Accounting — Trial Balance tab** — a two-number balance check (debit vs. credit); already fully legible as KPI cards, a 2-bar chart adds nothing.
- **Accounting — Journal Anomalies tab** — individual flagged transactions, not an aggregate; each row is its own case, not a category to compare.
- **Inventory — Stock Levels, Turnover, Reorder Point, Overstock & Stockout tabs** — genuinely per-SKU data with unbounded item counts (unlike the ≤20-category domains everywhere else); a bar per SKU would be an unreadable wall, not a chart. The table remains correct here.
- **Procurement — PO & Price tab** — skipped deliberately to avoid charting the same underlying price data twice: the Price Trend tab's `TrendChart` already covers this per-item series more cleanly (period-aggregated vs. raw price points).
- **Procurement — Cost Reduction tab** — a pairwise cheapest-vs-priciest comparison per item, already well-visualized via the existing two colored boxes; a bar chart would just re-encode the same two numbers.
- **Logistics — Delay Analysis and Route breakdown** — carrier×route groupings can be numerous and granular, the same per-item-list problem as Inventory's SKU tabs.
- **Operations — Bottleneck tab** — a multi-dimensional synthesis table (utilization + downtime + productivity + a flag per unit); it isn't a single ranked metric, so it stays a flagged table, which is the honest representation.

## 3. Motion — tied to real state changes only

- **Data-load entrance**: every new chart uses Recharts' `isAnimationActive` (bars grow in, donut segments sweep in, trend lines draw) triggered once by the real API response landing — not an idle loop. `KPICard`'s existing `useCountUp` (already established, reused unchanged) animates every hero/hero-adjacent number from its previous value to the new real one; `ProgressRing` (now applied to 4 more percentage KPIs this phase: Financial's two concentration ratios, Logistics's on-time rate) inherits the same count-up internally.
- **Sort/hover cross-highlight**: every newly-added `DepartmentBarChart`/`CompositionChart` that sits next to a real table reuses the exact `highlightedKey`/`onHoverChange` pairing already established in Phase 14 — hovering a bar or donut segment dims every other segment and highlights the matching table/`<details>` row; hovering the row does the reverse. Wired on: Financial's Revenue/Expense category tables, Financial's expense-by-department table, Accounting's General Ledger `<details>` list, Procurement's Supplier Spend table. Live-verified (see §5).
- **Trend charts deliberately do not get cross-highlight.** A continuous line doesn't have discrete "segments" the way a bar or donut slice does — pairing a period-table row hover to a moving point on a line chart would mean inventing a new interaction pattern this platform has never used, for a benefit that's marginal versus the categorical charts. Each `TrendChart` still has its own real hover tooltip (period, value, per-series color). This is a deliberate proportionality call, documented here rather than silently skipped.
- **No idle/ambient animation anywhere** — every animation fires once, on a real event (upload completing, tab switch remounting a chart, a hover), then settles.

## 4. Self-critique

Every new chart sits directly above (not replacing) its existing table — matching this platform's established "chart is for at-a-glance comparison, table is for exact figures and screen-reader access" discipline. None of the additions read as bolted-on: each was chosen from the module's *actual* returned data shape (verified via its real TypeScript interface, not guessed from the page's name), and every chart's numbers are the literal same values already rendered in the table beside it — no re-derivation.

One real bug was caught and fixed during verification, not shipped: `DepartmentBarChart`'s original fixed 36px right margin (fine for the short `%`-style labels it was built for) clipped longer currency-formatted labels like `SAR 48,690.00` once Financial/Accounting/Logistics/Operations started feeding it SAR values. Fixed by sizing the margin to the longest formatted label in the dataset (floored at the original 36px, so every pre-existing chart is pixel-identical).

## 5. Live verification

Backend (`python backend/api/main.py`) and frontend (`npm run dev`) started fresh; every check below driven by Playwright against the running app, not claimed from code alone.

- **All 11 newly-charted pages**, uploaded with real domain-matched test fixtures already in the repo (`financial_transactions_test_data.csv`, `accounting_gl_test_data.csv`, `inventory_transactions_test_data.csv`, `procurement_transactions_test_data.csv`, `logistics_shipments_test_data.csv`, `operations_units_test_data.csv`, `pay_equity_realistic_test_data.csv`, `contract_expiry_test_data.csv`, `job_pattern_title_test_data.csv`, `payroll_budget_test_data.csv`, `gosi_calculator_test_data.csv`) — **zero console/page errors** across all 11.
- **11 secondary tabs** with new chart work individually clicked into and screenshotted (Financial P&L, Accounting Balance Sheet + AR/AP Aging, Inventory ABC + Stock Aging, Procurement Price Trend + Supplier Score, Logistics Shipping Cost + Returns, Operations Quality + Utilization) — confirmed real values, correctly rendered `TrendChart`/`CompositionChart`/ordered-bucket charts. One test-script artifact was caught and ruled out during this pass: two donut screenshots initially looked like broken partial arcs; re-shot with a longer post-tab-switch settle wait confirmed this was the screenshot racing the chart's 600ms mount animation, not a real rendering bug — both render as proper full donuts.
- **Cross-highlight verified live, not just claimed**: hovering the first bar in Accounting Intelligence's General Ledger chart was confirmed via DOM query to highlight exactly 1 matching `<details>` element (the paired account row) — the bidirectional `highlightedKey`/`onHoverChange` wiring works end-to-end in the running app.
- **Computed-value integrity**: every chart's rendered numbers were cross-checked against the table directly beneath it in the same screenshot (e.g. Procurement's HELMET price-trend chart endpoint `16.0000` matches the `2026-01 → 2026-02` table row's `CURRENT AVG 16.0000` exactly) — no re-derived or approximated figures anywhere.
- Screenshots saved to `pw_shots_phase41/` (repo root) — 25 files covering every new chart, its secondary tabs, and the cross-highlight interaction states.

## 6. Regression count

| | Passed | Failed | Skipped |
|---|---|---|---|
| Before this phase | 1,232 | 9 (pre-existing, unrelated auth) | 1 |
| After this phase | 1,232 | 9 (same pre-existing auth failures) | 1 |

**Zero change** — this phase touched only `executive-ui/src` (2 new shared components, 1 new prop on an existing one, 11 page files). No backend file was modified, so the Python suite is byte-for-byte identical before and after, confirmed by re-running it. `npx tsc --noEmit` was run after every page's edits throughout this phase and stayed clean the entire way — no TypeScript regressions were introduced or silently accumulated.
