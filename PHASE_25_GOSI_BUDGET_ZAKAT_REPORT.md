# GOSI Calculator, Payroll Budget Planner, Zakat Estimator

Three new, financially-oriented modules — each its own separate page with its own nav
entry (explicitly not bundled into one tabbed page, unlike Phase 21's Labor Law
Calculators, per this brief's own UX correction). Internally these are labeled "Phase 37"
in code docstrings (following the codebase's own running phase counter, which had already
reached Phase 35.3/36 before this work started); this report keeps the filename requested
in the brief.

## 1. GOSI Contribution Calculator — confirmed rates and how System A/B was handled

**Confirmed via live search this phase** (current period: **July–December 2026**, the
period this module was built and verified against):

| | Employee | Employer | Total |
|---|---|---|---|
| **Old System** (Saudi, registered before 3 Jul 2024) | 9.75% | 11.75% | **21.5%** |
| **New System** (Saudi, registered on/after 3 Jul 2024) | 10.75% | 12.75% | **23.5%** |
| **Non-Saudi** | 0% | 2% (occupational hazards only) | 2% |

Contribution base (all rows above): **basic salary + housing allowance, capped at SAR
45,000/month**. New System rates rise 0.5pp every July until finalized around July 2028;
sources disagree on the exact 2028 endpoint (24%–25% combined found), so this module
deliberately does **not** hardcode a future rate table — it discloses the effective
period on every result and instructs reconfirmation via GOSI/Ta'meenati.

**A real correction to the brief's own preliminary research**: the brief assumed non-Saudi
employer contributions might have "no cap mentioned." Live search found multiple
independent sources confirming the **same SAR 45,000 cap applies to non-Saudi employer
contributions too** — corrected in
[`gosi_calculator_engine.py`'s module docstring](backend/core/gosi_calculator_engine.py#L20-L28)
and enforced in code (`GOSI_WAGE_CAP_SAR` applied uniformly, verified by
`test_wage_cap_applied_and_flagged`).

**System A/B ambiguity — "show both, don't guess," matching Phase 21's own precedent
exactly.** `_classify_gosi_system()`
([line 234](backend/core/gosi_calculator_engine.py#L234)) only classifies an employee's
system from an **explicit** system/tier column — it never infers System A/B from hire
date (registration date ≠ hire date reliably; guessing wrong produces a wrong real
government contribution figure). When no such column exists (the expected, common case),
**both** Old System and New System totals are computed and returned for every Saudi
employee (`old_system_total_sar`, `new_system_total_sar` always populated). For rollups
and the single "applicable" KPI figure, the **New System (higher) figure is used as the
conservative default** when unspecified — documented reasoning: an employer cost-planning
tool should never understate a mandatory cost. Live-verified: GEMP004 in the test fixture
(no system column value, wage capped at SAR 45,000) shows `applicable_system:
"unspecified_both_shown"` with both real figures exposed (Old: SAR 9,675; New: SAR
10,575) and the New System figure used for the applicable total — confirmed identically
in the browser screenshot (§5).

Full source list (5 independent sources + the disagreement note) in
[`GOSI_SOURCES`](backend/core/gosi_calculator_engine.py#L182-L206).

## 2. Payroll Budget Planner — input design decision

**Decision: manual entry per department, not a second uploaded planning file.** Reasoning
(full text in the
[module docstring](backend/core/payroll_budget_engine.py#L1-L44)):

- A second uploaded file (`Department + PlannedHeadcount + PlannedAvgSalary`) would force
  this module to fuzzy-match planning-file department names against this module's own
  normalized actual-data department names — exactly the "silent wrong join" risk
  `contract_expiry_engine.py`'s and `nitaqat_compliance_engine.py`'s cross-link functions
  explicitly refuse to take.
- A department list is low-cardinality (typically 5–20 rows) — small enough that manual
  entry is genuinely more usable than preparing a second file.
- The frontend fetches the REAL normalized department list from this module first (step
  1: upload → see real departments), then collects planned figures keyed by those EXACT
  labels (step 2: fill form → recompute) — there is never a name-matching step to get
  wrong.

**A correctness fix made mid-build**: the first draft computed
`actual_total_payroll_sar = actual_avg_salary × actual_headcount`, which silently imputes
the average salary onto employees whose salary was excluded (range-text, etc.) — exactly
the kind of approximation this session's other modules refuse. Fixed to the REAL sum of
only clean numeric salaries found
([`payroll_budget_engine.py:243-247`](backend/core/payroll_budget_engine.py#L243-L247));
`n_excluded_invalid_salary` discloses when the real total may understate the true one.
Verified by `test_actual_totals_are_real_sum_not_imputed` (IT department: 3 employees, 1
with a range-text salary — actual total is exactly SAR 32,000 = 15,000+17,000, never
SAR 48,000 = avg×3).

`department_normalizer.py` is genuinely reused (not reimplemented) for the actual-data
side, which is also what makes the manual-entry design's join-safety guarantee work.
Departments with actual data but no submitted budget, and planned entries with no actual
headcount, are both explicitly flagged (`planned_submitted: false` /
`actual_present: false`) — never assumed a zero budget or silently dropped.

## 3. Zakat Base Estimator — investigation findings and scoping decision

**Investigation (live search, 5 rounds) found the real ZATCA 2024 Bylaws methodology is
materially more complex than the brief's own draft formula.** Specifically:

- The base starts from a **difference between book net profit and adjusted net profit**
  (not simply net income), adds equity/equity-like items and *qualifying* non-current
  liabilities, then deducts a list of **12+ individually-defined deductible asset
  categories** (qualifying investments, non-available-for-sale raw materials, net fixed
  assets, non-trading intangibles, employee housing assets, statutory deposits, deferred
  tax assets, qualifying sukuk/bonds, investment properties not held for sale, assets
  under concession arrangements, capital projects under construction not for sale,
  right-of-use assets, qualifying overdue government receivables), each with its own
  eligibility test.
- A **minimum/maximum base comparison** applies depending on whether adjusted net profit
  exceeds book net profit — a branch a short form cannot represent.
- Liabilities are netted **category-by-category** against specific asset classes (current
  vs. current, non-current vs. non-current), not simply summed and subtracted.

**Decision taken: scope down to an explicitly-labeled SIMPLIFIED TRADITIONAL formula, ship
it, but never call it ZATCA-compliant.** The brief's own fallback menu was "scope down
further... or stop and report." A traditional approximation (Equity + Long-Term
Liabilities/Provisions − Net Fixed Assets − Other Deductions) is independently,
repeatedly cited across multiple sources found this phase as a widely-used *starting-point*
approximation, in the same spirit as this platform's existing "illustrative, not
authoritative" modules (Nitaqat's Saudization estimate). What makes this responsible
rather than misleading is that the gap to the real methodology is disclosed **explicitly
and specifically** (the actual 12+-category list above, not generic "consult a
professional" boilerplate) in every result — available or not — and the module never
claims ZATCA compliance anywhere in its output
([`METHODOLOGY_GAP_NOTE_EN`/`_AR`](backend/core/zakat_estimator_engine.py#L163-L182),
rendered on the page in a critical-tone banner, not just in code). This is documented as a
genuinely different judgment call from the HR Letter Generator phase's disciplinary-letter
exclusion (there, no simplified version is safe because the harm lands on a named
individual with no mitigating context; here, a clearly-labeled directional planning number
carries materially lower risk provided the labeling is honest).

**No dataframe/upload anywhere in this module** — a 4-field manual balance-sheet entry
form is the entire interaction surface, matching the brief's own instruction that this is
a genuinely different data shape (company-level financial statement, not employee rows).
Strict non-approximation: `total_equity_sar`, `long_term_liabilities_provisions_sar`, and
`net_fixed_assets_sar` are required — any missing field is named exactly, never
zero-defaulted (`test_missing_field_never_silently_zeroed`). `other_deductions_sar`
defaults to 0.0 only because "no additional deductions" is a legitimate user assertion,
unlike a missing balance-sheet figure.

## 4. Test results

```
$ py -m pytest tests/test_gosi_calculator_engine.py tests/test_payroll_budget_engine.py tests/test_zakat_estimator_engine.py -v
...
16 + 15 + 12 = 43 passed
```

- **GOSI (16 tests)**: hand-computed Old/New System figures, non-Saudi 2%-employer-only,
  wage-cap application and flagging, range-text salary refusal, unclassifiable-nationality
  exclusion, department rollup (via genuine `department_normalizer.py` reuse — "IT"/"HR"
  correctly expand to canonical labels), no raw employee ID in output.
- **Payroll Budget (15 tests)**: real-sum-not-imputed actual totals, department and
  company-wide variance hand-computed against a synthetic fixture, "actual but no plan"
  and "plan but no actual" both correctly flagged rather than fabricated, no-plan-submitted
  company variance is `None` not `0`.
- **Zakat (12 tests)**: hand-computed base/liability, base floored at zero, missing
  required fields named individually (single and multiple), methodology-gap disclosure
  present on both available and unavailable results, sources cited.

## 5. Live verification — real running backend + real browser

**A pre-existing "stale socket" issue (documented in Phase 21's own report) recurred**:
two Python processes were both listening on port 8000, one without `--reload`. The
non-reloading process was serving requests and returning 404 for the new routes despite
the code being correct. Terminated the stale process (PID 11148); the remaining
`uvicorn --reload` process immediately served all three new endpoints correctly — the
same class of environment issue previous phases hit, resolved the same way.

**Direct HTTP against the live backend** (all 3 endpoints, 200 OK): GOSI calculator on
the real fixture (5/7 employees computed, matching the test suite exactly); Payroll
Budget variance (both the actual-only call and the planned-budget call); Zakat estimator
(both the computed case, SAR 4.00M base, and the missing-field case).

**Browser (Playwright/Chromium, real clicks, zero console errors across the whole
session):**
1. **GOSI Contribution Calculator** — uploaded the fixture, confirmed KPIs (5 computed, 1
   excluded, SAR 18.0K total, 3 Saudi/2 non-Saudi), department breakdown table (Finance
   SAR 13.2K, IT SAR 4.2K, HR SAR 400, Sales SAR 190 — all matching hand computation),
   employee-level detail table showing the "Both shown" caution badge for the
   unspecified-system employee with both Old (SAR 9.7K) and New (SAR 10.6K) system
   figures visible side by side, and the wage-cap asterisk flag on the capped row.
2. **Payroll Budget Planner** — uploaded the fixture, saw real actual figures per
   department (7 headcount, SAR 71.0K actual payroll) with an inline editable planned-
   headcount/planned-salary form seeded from the exact same normalized department names;
   entered Finance (2, 10000) and IT (3, 15000), clicked "Compute Variance," and got
   +SAR 2.0K (Finance) / −SAR 13.0K (IT) / **+SAR 6.0K, +9.2% company-wide** — exact match
   to hand computation and the test suite.
3. **Zakat Base Estimator** — landed on a form-only page (no upload dropzone anywhere),
   prominent critical-tone methodology-gap banner rendered above the form; entered
   5,000,000 / 1,200,000 / 2,000,000 / 200,000 and got **SAR 4.00M base, SAR 100.0K
   liability (2.5%)** — exact match; then cleared Total Equity and re-submitted — got the
   honest "Cannot compute — required field(s) missing: Total Equity" banner, **no
   fabricated figure**, confirming the strict non-approximation path live, not just in
   tests.
4. Sidebar confirmed correctly placed: GOSI directly after Saudi Labor Law Calculators;
   Payroll Budget Planner directly after Payroll Movements; Zakat in a new standalone
   "Financial Planning" section (its own group, since — per the investigation in §3 — it
   shares no data shape with any other module on the platform, the same reasoning the
   brief itself anticipated).

## 6. Full regression suite

```
$ py -m pytest tests/ -q --ignore=tests/_smoke_test.py
1 failed, 1562 passed, 1 skipped, 205 warnings in ~65s
```

The single failure (`test_phase29_extended.py::TestCEODashboardVisualisations::
test_health_wheel_imported`) is the same pre-existing, unrelated failure noted in the
prior phase's report — untouched by this work. **Zero regressions.** 1562 passed = 1519
pre-existing + 43 new tests this phase.

`npx tsc --noEmit` and `npm run build` both pass cleanly (build in 18.13s).

## Files changed

- `backend/core/gosi_calculator_engine.py` (new, ~460 lines)
- `backend/core/payroll_budget_engine.py` (new, ~330 lines)
- `backend/core/zakat_estimator_engine.py` (new, ~230 lines, no dataframe dependency)
- `backend/api/local_analysis_routes.py` (+~260 lines) — 3 new endpoint groups:
  `POST /gosi-calculator`, `POST /payroll-budget-variance` (accepts optional
  `planned_budgets` JSON form field), `POST /zakat-estimator` (JSON body, no file)
- `tests/test_gosi_calculator_engine.py` (new, 16 tests)
- `tests/test_payroll_budget_engine.py` (new, 15 tests)
- `tests/test_zakat_estimator_engine.py` (new, 12 tests)
- `gosi_calculator_test_data.csv`, `payroll_budget_test_data.csv` (new fixtures, repo root)
- `executive-ui/src/pages/GosiCalculator.tsx`, `PayrollBudgetPlanner.tsx`,
  `ZakatEstimator.tsx` (new — three separate pages, no shared tab component)
- `executive-ui/src/types/index.ts`, `App.tsx`, `layout/Sidebar.tsx` (+3 `NavPage`
  variants, routing, 3 nav entries: GOSI after Saudi Labor Law Calculators, Payroll
  Budget Planner after Payroll Movements, Zakat in a new "Financial Planning" group)
