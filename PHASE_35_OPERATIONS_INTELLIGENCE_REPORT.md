# Phase 35 — Operations Intelligence Phase 1 (Business Intelligence Suite, Module 6, final)

Operations Intelligence is the sixth and final originally-planned Business Intelligence module:
productivity, utilization, downtime, and operational quality across departments/branches/
production lines/machines.

---

## 1. Step 0 — Data Shape Design and Reasoning

Unlike every prior module (each had one obvious real-world shape: shipments, purchase orders,
inventory transactions, GL entries), operations data has no single canonical shape — a factory's
downtime log looks nothing like a service branch's productivity log. Rather than inventing one
rigid schema, this module works from a generic **operational-unit-per-period record**
(`backend/core/operations_intelligence_engine.py:1-33`):

| Field | Required? |
|---|---|
| Unit (department/branch/production-line/machine — whatever the data calls it) | required |
| Period | required for trend and bottleneck-confidence views |
| Output/production count | required for productivity and cost-per-unit |
| Hours operated | required for productivity and utilization |
| Hours available (capacity) | required for utilization — **never assumed** |
| Downtime hours | required for downtime analysis |
| Downtime reason/cause (free text or already-categorical) | optional — enables cause breakdown |
| Defect count (+ output), or a direct quality-score/defect-rate column | required for quality analysis |
| Operating cost | required for cost-per-unit-of-operation |

Every one of the six items is independently gated on its own real column requirements — none
requires all fields, and each degrades honestly on whatever honest subset is present (proven live
in §7 by dropping just `HoursAvailable` and watching only utilization, and everything that depends
on it, go unavailable while productivity/downtime/quality/cost stayed intact).

---

## 2. The 6 Items Built — Methodology and Honest Degradation

All in `backend/core/operations_intelligence_engine.py` (1,050 lines).

| # | Item | Methodology | Honest-degradation behavior |
|---|---|---|---|
| 1 | **Productivity** (`_productivity_from_records`, line 353) | `output ÷ hours operated`, per unit | Unavailable without both an output and hours-operated column |
| 2 | **Utilization** (`_utilization_from_records`, line 417) | `hours operated ÷ hours available × 100` | **Never estimated with an assumed default capacity** — unavailable without a real hours-available column, exactly as the brief required |
| 3 | **Downtime Analysis** (`_downtime_from_records`, line 507) | Total/per-unit downtime hours + rate; cause breakdown auto-detects whether the reason column is already-categorical (direct value-count breakdown) or genuinely free text (TF-IDF theme extraction, reusing Exit Interview's machinery — see §3) | Unavailable without a downtime-hours column; cause breakdown specifically degrades (with total downtime still shown) below the 5-reason or 3-mention floors |
| 4 | **Quality/Defect Analysis** (`_quality_from_records`, line 635) | `defects ÷ output` (or a direct quality-score column), plus period-over-period variance reusing the exact shape from Phase 30/31/33/34's variance dataclasses | Unavailable without defect+output data or a direct quality-score column; trend specifically omitted below 2 periods |
| 5 | **Bottleneck Identification** (`_bottleneck_from_results`, line 753) | Ranks units by utilization; flags a unit as a confident bottleneck only when it has ≥3 periods of data AND sits ≥15 percentage points below the fleet average (computed only from sufficient-sample units) | Units below the 3-period floor show real numbers but never the confident flag — proven live with Line-4 (worse raw utilization than the flagged Line-3, but only 2 periods) |
| 6 | **Cost per Unit of Operation** (`_cost_per_unit_from_records`, line 832) | `operating cost ÷ output`, per unit | Unavailable without both cost and output columns — see §4 for the ownership decision |

---

## 3. Downtime-Cause Theme Extraction — Third Reuse of the TF-IDF Machinery

Same genuine-reuse discipline as Phase 34: `scrub_pii()`, `extract_top_terms_tfidf()` /
`extract_top_terms_word_frequency()`, `SKLEARN_AVAILABLE`, `MIN_DOCUMENT_FREQUENCY` (3), and
`MIN_RESPONSES_FOR_AGGREGATE` (5) — all promoted to public functions in
`exit_interview_intelligence_engine.py` during Phase 34 — are imported directly here, now used
across a **third** domain (Exit Interview → Logistics Returns → Operations Downtime). A fresh,
downtime-specific theme dictionary (`_DOWNTIME_THEME_KEYWORDS`, line ~152: Mechanical Failure,
Material Shortage, Changeover/Setup, Scheduled Maintenance, Power Outage) was built — the HR
attrition dictionary would never match downtime-cause language.

**New this phase**: a categorical-vs-free-text auto-detector (`_CATEGORICAL_UNIQUE_RATIO_THRESHOLD`
/ `_CATEGORICAL_AVG_LEN_THRESHOLD`, line ~157) that checks whether the reason column's distinct-
value ratio and average string length look like a small fixed vocabulary (e.g. "Maintenance",
"Setup") rather than genuine free text. When it does, the module skips TF-IDF entirely and reports
a direct category value-count breakdown instead — never forcing a text-mining pipeline onto data
that's already structured. Verified by a dedicated test
(`test_categorical_reason_column_skips_tfidf`) using a synthetic 2-value categorical column.

---

## 4. Cost-Per-Unit-of-Operation — Ownership Decision (Operations vs. Financial Intelligence)

**Built here, deliberately, not deferred.** The reasoning (documented in the module's own
docstring, `backend/core/operations_intelligence_engine.py:1-38`, and surfaced live in the UI's
Cost per Unit tab banner):

- Financial Intelligence (Phase 30) owns company-wide expense-category and P&L analysis from a
  plain transaction list — it has no concept of "units of output" to divide cost by.
- Cost-per-unit-of-operation requires **joining** an operating-cost figure to a production/output
  figure at the operational-unit level — a join only this module's upload shape can make.
- The two are complementary, not duplicative: a user wanting "what did we spend on rent this
  quarter" goes to Financial Intelligence; a user wanting "how much does it cost Line-3 to
  produce one unit of output" goes here. Neither module could answer the other's question from its
  own upload shape.

This mirrors the same ownership-boundary discipline Phase 32 used for its flagged (but
undecided/deferred) carrying-cost question — the difference here is the decision was actually
reachable and is built, not left open.

---

## 5. Fixture Design

`operations_units_test_data.csv` (repo root, 26 unit-period records, 5 units, 2025-11 to 2026-04)
— built via a scratch script, cross-verified with pandas before any test was written:

- **Genuine utilization variance**: Line-1 (90.08%, best) down to Line-4 (39.50%, worst raw
  number) — a real spread, not clustered around one value.
- **Bottleneck vs. insufficient-sample contrast (item 5's core test)**: Line-3 has full 6-period
  data at 44.33% utilization (28.02 points below the 72.35% fleet average) → confidently flagged.
  Line-4 has a *worse* raw utilization (39.50%) but only 2 periods → deliberately NOT flagged,
  proving the minimum-sample discipline actually gates the label and isn't just decorative.
- **Real, worsening quality trend**: Line-3's defect rate genuinely rises period over period
  (8%→9%→10%→11%→12%→13%), driving the fleet-wide overall defect rate from 2.92% (Nov 2025) to
  4.00% (Apr 2026) — a real trend from real per-period data, not a flat number dressed up as one.
- **Downtime-cause theme diversity**: 26 free-text downtime-reason entries span 5 themes; four
  (Changeover/Setup=8, Mechanical Failure=7, Material Shortage=5, Scheduled Maintenance=5) clear
  the 3-mention floor; a fifth (Power Outage=1) is deliberately below it, proving suppression
  actually triggers.
- **Downtime decoupled from the bottleneck story's engineering**: Line-3's downtime is
  concentrated in mechanical-failure language specifically, while Line-1's is all routine
  changeover — the cause breakdown genuinely differentiates units, not just totals.

---

## 6. Test Results

**New tests**: `tests/test_operations_intelligence_engine.py` — 33/33 passing, organized into 8
sections covering all 6 items' hand-computed figures (including the categorical-vs-free-text
auto-detection and the bottleneck-vs-insufficient-sample contrast), cross-module honest
degradation against all five prior BI-suite fixtures, and bundle/serialization sanity.

**Full regression suite**: `1786 passed, 1 skipped, 1 failed` (the same pre-existing, unrelated
`test_health_wheel_imported` failure present before this phase — 1753 baseline + 33 new tests =
1786). **Zero regressions.**

---

## 7. Live Browser Verification

Playwright run against the live backend + Vite dev server. Zero console/page errors
(`CONSOLE_ERRORS: []`).

| Screenshot | Confirmed |
|---|---|
| Productivity tab | Line-1 highest (10.00 units/hr), Line-3/Line-4 tied lowest (7.00) — exact match |
| Utilization tab | 39.5% / 44.3% / 75.0% / 80.0% / 90.1% across all 5 units — exact match |
| Downtime tab | 1,569 hrs total; per-unit breakdown; TF-IDF cause breakdown with all 4 themes at exact counts, "Power Outage" correctly absent — exact match |
| Quality tab | 3.39% overall defect rate; per-unit rates; 5-row trend table all showing positive (worsening) changes — exact match |
| **Bottlenecks tab** | Line-3 (6 periods, 44.3% util) shows a red "Bottleneck" badge; Line-4 (2 periods, 39.5% util — objectively worse) shows "Insufficient data" instead — the core proof that the minimum-sample discipline actually gates the UI, not just the API |
| Cost per Unit tab | SAR 5.02–13.02 range across units; ownership-boundary banner vs. Financial Intelligence displayed | 
| Honest degradation: dropping `HoursAvailable` | Utilization tab shows exactly one missing checklist item ("Hours available / capacity... never assumed"), everything else detected; Bottlenecks tab correctly cascades to unavailable since it depends on utilization |
| Cross-module: uploading Logistics' fixture | "No operational-unit column detected... every figure in this module is keyed by unit" — correctly unavailable |

---

## 8. Phase 2 Backlog

- **True SLA-compliance tracking** — explicitly deferred, as specified. This platform has no way
  to know contractually-defined SLA targets unless the upload explicitly provides them. If a real
  SLA-target column is ever detected in a future upload, that would be a plausible, easy Phase 2
  addition — but this phase does not assume or default one.
- **Predictive/forecasting capability** for any of the six items — explicitly deferred, consistent
  with every other Business Intelligence domain (Phase 30–34) deferring forecasting.

No other items from the requested scope remain outstanding — all 6 were built this phase.

---

## Regression Count

**1786 passed, 1 skipped, 1 pre-existing unrelated failure. Zero regressions.**

## Environment Note

Same dev-environment ghost-socket condition as Phases 30-34; `executive-ui/vite.config.ts`'s
proxy target (pointed at the LAN IP since Phase 31) was reused unchanged.
