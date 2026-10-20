# Phase 16 — Verify-Then-Build: Benchmark, Simulation & Drift Engines

Status: **Complete. Of the three flagged engines, two (`workforce_simulation_engine.py`,
`workforce_forecasting_engine.py`) turned out to be REAL & USABLE — and were
already fully built and live in the product (not dormant at all). The third
(`benchmark_engine.py`) is PLACEHOLDER-DRESSED-AS-REAL, and — more
importantly — that placeholder data is already shipping live on the
Executive Dashboard, actively telling users "≥5 organisations" and
"k-anonymity ≥5 enforced" for what is really one hardcoded seed row per
sector. `drift_monitor.py` is real but-comment-admitted-partial code that
is never called anywhere in the live application. No new "Scenario
Planning" UI was built, because it already exists — instead, this phase's
real work was auditing the one already-shipped feature built on fabricated
data, and in the process finding and fixing two additional, independent
functional bugs that had nothing to do with the fabrication issue.**

---

## Step 1 — Reality-check verdicts

### 1. `benchmark_engine.py` — **PLACEHOLDER-DRESSED-AS-REAL**

- **`_SEED_BENCHMARKS`** (`benchmark_engine.py:46-143`): 8 hardcoded rows
  of sector figures (WSI/RHI/TFRI/HCRI means, `cost_per_departure_sar_mean`,
  etc.) for banking/oil_gas/telecom/government/retail_fmcg/healthcare. The
  only provenance given is a vague comment (`benchmark_engine.py:39-44`):
  "derived from: Public Vision 2030 workforce reports, Saudi Labour Market
  data (HRSD), Global HR analytics benchmarks adapted for Saudi context" —
  no URL, no report name, no date, no page reference. Not a citation.
- **The fabrication is compounded by a misleading field**: every seed row
  carries a hardcoded `n_contributors: 5-7` (`benchmark_engine.py:48,60,72...`)
  — i.e. each row *claims* to already be an aggregate of 5-7 real
  organisations. It is one internal estimate. The k-anonymity gate
  (`n_contributors >= _K_MIN`, `benchmark_engine.py:350`) is real, executable
  code, but it is checking a fabricated count, so it passes trivially and
  protects nothing.
- **The DP-noise math is real** (`_dp_noise()`, `benchmark_engine.py:276-280`
  — genuine Gaussian-approximation Laplace mechanism, actually executes on
  every read) — but it's adding real privacy noise to a fake number, which
  is privacy-math theater around fabricated data, not a genuine
  differentiator.
- **Structural point, not just "didn't find a citation"**: WSI/RHI/TFRI/HCRI
  are this platform's own proprietary composite indices (see
  `employeeRiskStore.ts`'s `ExecutiveIndexResult`) — no external Saudi/GCC
  survey could ever validly publish a "sector average WSI" because WSI is
  not a metric any outside body computes. This isn't a search that might
  succeed with more effort; it's asking for a benchmark of a number that,
  by construction, only exists inside this app.
- **`compare_internal_departments()`** and **`get_historical_position()`**
  (`benchmark_engine.py:609-770`) are a different story — both are
  genuinely real, using only the org's own uploaded department data or its
  own historical snapshots, zero external fabricated data involved. Neither
  is wired to any API route (confirmed via grep — zero callers). Real,
  unused, a candidate for a future phase, not built on here since it's
  outside what Step 2 asked for.

### 2. `workforce_simulation_engine.py` — **REAL & USABLE, already live**

`run_workforce_simulation()` (`workforce_simulation_engine.py:292-509`)
computes real scenario impacts from actual ML feature importance
(`ml_validation.conservative.feature_importance`) and real risk-driver
frequency (`org_risk_driver_summary.top_org_risk_drivers`) against the
actual uploaded dataset — not canned numbers. It reuses the canonical,
cited cost model (`estimate_departure_cost` from
`financial_intelligence_engine.py`, per `workforce_simulation_engine.py:21-26`)
instead of a separate hardcoded floor. Confidence tiers are derived from
real thresholds on real feature weights (`_confidence()`,
`workforce_simulation_engine.py:260-265`). Caps are disclosed as
conservative bounds, non-causal framing is explicit throughout.

**Already wired end-to-end**: `local_analysis_routes.py:997-1009` calls it
on every analysis; the frontend has a full page for it —
`SimulationPanel.tsx`, the "Scenario Planning" nav item. Not dormant.
Verified live with real data (screenshot §3).

### 3. `workforce_forecasting_engine.py` — **REAL & USABLE, already live**

`generate_workforce_forecast()` (`workforce_forecasting_engine.py:66-207`)
computes a real standard deviation from actual scored records
(`_safe_std()`), derives 3 honestly-labeled scenario projections from that
real spread (not fabricated trend data), and flags real
escalation-candidate departments from actual per-department risk-band
percentages (`_find_escalation_depts()`, ≥15% Priority Review or ≥60 avg
risk — real thresholds against real numbers). Confidence is unconditionally
"low — single snapshot," and the governance note is explicit that these are
projections, not predictions.

**Already wired end-to-end**: `local_analysis_routes.py:961-968` calls it
on every analysis; already surfaced in `DecisionCenter.tsx` and
`ExecutiveDashboard.tsx`. Not dormant. Verified live (screenshot §3).

### 4. `drift_monitor.py` — **Real code, never called, and the specific audited claim isn't implemented**

The module's own docstring is self-honest: *"Current state: interfaces +
hooks implemented; statistical tests are architecture stubs ready for
enterprise data integration"* (`drift_monitor.py:151-152`).

- `check_schema_drift()` (`drift_monitor.py:239-295`) is genuinely complete
  — real column-set and dtype comparison against a stored baseline.
- `check_feature_drift()` and `check_prediction_drift()`
  (`drift_monitor.py:297-399`) use a simple relative-mean-shift check, with
  an explicit code comment admitting the gap: *"production: add PSI/KS
  test"* (`drift_monitor.py:300`) and *"HOOK: replace with PSI... in
  production"* (`drift_monitor.py:366`). The PSI/KS tests the original
  audit specifically named are **not implemented** — only a cruder mean-shift
  proxy exists.
- **Zero live callers**: grepped the entire backend — `drift_monitor.py` is
  imported nowhere except a standalone smoke-test file
  (`_smoke_test.py:263`). `set_baseline()` is never called by any analysis
  pipeline, so even the well-built schema-drift logic never actually
  executes against real data in this product.

---

## Step 2 — What was built

### `benchmark_engine.py`: not activated further — and the already-live instance was fixed

Per the instructions for a placeholder-dressed engine, I did a live web
search rather than guessing:
- *"Saudi Arabia GASTAT employee turnover cost per departure sector
  benchmark 2025"*
- *"Saudi Arabia sector employee turnover rate banking oil gas telecom
  government free report 2024 2025"*
- *"cost of turnover" / "cost per hire" Saudi Arabia SAR report... citable 2024*
- Fetched the one candidate with real numbers behind a citable-looking
  academic source (a GOSI-data turnover study) — its abstract discloses no
  actual per-sector figures.

Result: no freely-citable per-sector cost/turnover benchmark found — this
matches, and does not overturn, the prior Phase 35.4 search already
documented in `financial_intelligence_engine.py:70-107`, which found the
same negative result for the adjacent salary-by-industry-vertical table and
left it honestly labeled `uncalibrated_generic_estimate`. The commercial
results that did turn up (EOR/payroll vendor blog posts quoting
SAR 50,000–100,000-style figures) are exactly the class of uncited
marketing-copy source this codebase's own established discipline already
rejects (see the Hays/Mercer/Korn Ferry/GulfTalent exclusion at the same
citation). **`benchmark_engine.py` was not wired into
`financial_intelligence_engine.py`** — the existing honest
`uncalibrated_generic_estimate` fallback used by Overtime Cost Intelligence
and Recruitment's cost-per-hire is untouched.

**But this engine is not actually dormant** — `ExecutiveDashboard.tsx`
already calls `/api/local/benchmarks/compare` and renders the result via
`BenchmarkGapPanel`, live, today. That panel was telling users their
comparison was backed by "≥5 organisations" with "k-anonymity ≥5
enforced," when the underlying data is the seeded placeholder described
above. Per this phase's explicit mandate — *"do NOT build on top of
anything that turns out to be placeholder/uncalibrated without fixing that
first"* — this already-shipped honesty gap was fixed:

- **`benchmark_engine.py`**: `compare()` now selects between two governance
  notes based on `bm.is_seeded` (`benchmark_engine.py:404-426,448-451`). The
  seeded note explicitly states the reference is *"this platform's own
  internal illustrative estimate — NOT yet backed by real client
  contributions, despite the displayed contributor count"* and clarifies
  the DP/k-anonymity code is real but "currently protect[s] a seeded
  placeholder, not real cross-organisation data."
- **`BenchmarkGapPanel.tsx`**: now reads `comparison.benchmark.is_seeded`
  and, when true, replaces the "≥N organisations" chip with "Illustrative
  sector reference" and swaps the footer's privacy-math claim for the
  same honest disclosure as the backend. Verified live (screenshot below).
- **`local_analysis_routes.py:2442-2449`**: updated the `/benchmarks/sectors`
  docstring itself so a future engineer reading the route doesn't inherit
  the same misconception.

### Two additional, independent bugs found and fixed while verifying this panel

Neither is a fabrication issue — both are why the already-shipped panel
never worked correctly even on its own (fake) terms:

1. **State-mutation bug** (`ExecutiveDashboard.tsx`): `onRequestComparison`
   did `;(riskData as any).benchmarkComparison = json.comparison` — a
   direct mutation of a context object, invisible to React. The real API
   call succeeded (confirmed via direct `curl`), but clicking a sector
   never visibly updated the panel. Fixed with a real `useState`
   (`benchmarkComparison`), wired into the `BenchmarkGapPanel` prop and the
   fetch handler.
2. **camelCase/snake_case field mismatch**: the panel sent
   `org_data: riskData` wholesale — `riskData` is camelCase
   (`totalEmployeeRecords`, `riskBandCounts`, `executiveIndices`) but
   `benchmark_engine.py`'s `compare()` reads snake_case keys
   (`total_employee_records`, `risk_band_counts`, `executive_indices`).
   Every `.get()` on the backend silently missed, so **every user who ever
   used this panel saw their own organisation's values as a flat 0.0**,
   regardless of real data. Fixed by mapping the exact fields the backend
   reads instead of forwarding the raw object.

Both confirmed fixed via live screenshot (§3) — before the fix, clicking
"Banking" changed nothing visible; after, the panel shows real org values
(e.g. WSI 65.9, RHI 82.5 — matching the uploaded dataset) against the
now-honestly-labeled seeded sector reference.

### `workforce_simulation_engine.py` / `workforce_forecasting_engine.py`: no new feature built

Both are already fully wired and live (`SimulationPanel.tsx` /
"Scenario Planning" nav item; `DecisionCenter.tsx`). Building a duplicate
"what happens if overtime dropped 20% in Sales" UI on top of an
already-existing, already-correct Scenario Planning page would be pure
duplication. Instead, this phase re-verified the existing feature actually
works end-to-end with real uploaded data (§3) rather than assuming the
premise that it needed to be built.

### `drift_monitor.py`: not built on, one line why

**Not worth activating in this phase.** Three reasons, each independently
sufficient: (1) zero live callers — activating it means designing a new
"set a baseline, then compare future uploads" ceremony this stateless,
upload-once product doesn't currently have, which is a new workflow
concept, not a UI surface on top of existing computation; (2) the
specific PSI/KS statistical tests the original audit named are explicitly
unimplemented (`drift_monitor.py:300,366`) — only a cruder mean-shift proxy
exists; (3) the one immediately real, low-effort angle (comparing a new
upload's schema against the earliest snapshot already stored by
`AnalysisHistory.tsx`) would still require deciding storage/privacy
implications of persisting feature-level statistics over time — not a
"small, scoped" addition as instructed. Per the explicit "nice-to-have if
real, not a priority to force if thin" guidance, this is deferred rather
than forced.

---

## 3. Live verification (screenshots)

All captured via Playwright with real data (`test_employee_data.csv`, 200
employees), zero console errors across the full run.

- **Sector Benchmark Comparison, before any fix**: clicking "Banking"
  produced no visible change (state-mutation bug) — confirmed by direct
  `curl` to `/api/local/benchmarks/compare` that the backend call itself
  succeeded and returned data the UI simply never rendered.
- **After all three fixes** (`scratchpad/p16/benchmark_after_click.png`):
  panel now shows "Sector: Saudi Banking," "Q2_2026," and an
  **"Illustrative sector reference"** chip (replacing "≥5 organisations").
  Real org values render correctly — Workforce Stability Index Org 65.9 vs.
  Sector 69.0, Retention Health Index Org 82.5 vs. Sector 106.9, etc. —
  confirming the camelCase/snake_case fix. Footer text reads the new honest
  disclosure in full.
- **Scenario Planning** (`scratchpad/p16/scenario_planning.png`): real
  8-intervention list, correctly differentiated confidence tiers ("high"
  for interventions with real feature-importance support, "low — No data
  support" honestly shown for the others), a computed Recommended Strategy
  combining the top 3 with real percentages (-8.0%, -7.0%, -3.9%), real
  baseline (Avg Risk 29.4, Avg Stability 70.7).
- **Decision Center** (`scratchpad/p16/decision_center.png`): real
  CEO/CHRO narratives computed from the actual 200-employee dataset,
  correct department name ("Sales"), correct ML validation figures
  (ROC-AUC 0.54, MCC 0.11), governance disclaimers intact.

## 4. Regression suite

`python -m pytest tests/ -q` → **1353 passed, 40 failed, 1 skipped**.

All 40 failures confirmed pre-existing and unrelated to this phase:
- 39 in `test_phase30_1_security.py` — root cause confirmed via direct
  reproduction: `passlib.exc.MissingBackendError: bcrypt: no backends
  available` — a missing `bcrypt` package in the venv, an environment
  issue untouched by anything in this phase.
- 1 in `test_phase29_extended.py::test_health_wheel_imported` — asserts
  `CEODashboard.tsx` still imports `WorkforceHealthWheel`, a component
  replaced by `WorkforceCompositionRiver` back in Phase 12 (long before
  this session) — a stale test, not a regression.

Targeted re-run of every test file covering the files touched this phase
(`test_sector_benchmarking_phase4.py`, `test_financial_intelligence_engine.py`,
`test_phase22_workforce_simulation.py`, `test_phase27_simulation.py`,
`test_phase27b_simulation_activation.py`) — **98 passed, 0 failed.**

Frontend: `npx tsc --noEmit` clean after every edit.

## 5. Files changed

`backend/core/benchmark_engine.py` (honest governance-note branching),
`backend/api/local_analysis_routes.py` (docstring only),
`executive-ui/src/components/visualizations/BenchmarkGapPanel.tsx`
(honest seeded-vs-real disclosure), `executive-ui/src/pages/ExecutiveDashboard.tsx`
(state-mutation fix + camelCase/snake_case field-mapping fix).

No changes to `workforce_simulation_engine.py`, `workforce_forecasting_engine.py`,
or `drift_monitor.py` — all three were left exactly as found, per their
respective verdicts above.
