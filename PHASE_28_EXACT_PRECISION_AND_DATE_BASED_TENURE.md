# Phase 28 — Exact Display Precision + Date-Based Tenure Calculation

Two direct fixes to the Saudi Labor Law Calculators module, both following
`Copy of EOS Report.xlsx`'s exact methodology with no alternative rounding
scheme or reinterpretation.

## Fix 1 — Exact SAR display precision (Gratuity, Leave Balance, WPS Consistency)

**Problem.** `SaudiLaborLawCalculators.tsx`'s local `sar()` formatter
K-abbreviated every amount ≥ SAR 1,000 to one decimal place (e.g. `SAR
20.3K` for an actual value of `20,564.38`). Since these three tabs compute
real legally-owed amounts — not illustrative estimates, per this module's
own "real legal payment, not an illustrative estimate" framing — the
rounding hid precision the backend already computed correctly, making it
impossible for the user to verify a displayed figure against their
reference Excel.

**Fix.** [SaudiLaborLawCalculators.tsx:171-176](executive-ui/src/pages/SaudiLaborLawCalculators.tsx#L171-L176):

```ts
// Before
function sar(n: number): string {
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(1)}K`
  return `SAR ${n.toFixed(0)}`
}

// After
function sar(n: number): string {
  return `SAR ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
```

Scope: this file contains only the Gratuity, WPS, and Leave Balance tabs —
no other module's formatter was touched. Overtime Cost Intelligence, Sector
Benchmarking, and every other illustrative-estimate module keep their own
independent K-rounded formatters unchanged.

**Before/after** (live screenshots in `SCREENSHOTS/phase28_gratuity_exact_precision.png`
and `SCREENSHOTS/phase28_leave_exact_precision.png`):

| Location | Before | After |
|---|---|---|
| Gratuity table, Full Award | `SAR 20.6K` | `SAR 20,564.38` |
| Gratuity table, If Resignation | `SAR 6.9K` | `SAR 6,854.79` |
| Gratuity KPI, Total Full-Award Exposure | `SAR 64.6K` | `SAR 64,565.75` |
| Leave Balance table, Compensation | `SAR 9.5K` | `SAR 9,524.98` |
| Leave Balance KPI, Total Compensation Exposure | `SAR 14.0K` | `SAR 14,024.98` |

## Fix 2 — Date-based tenure takes priority over `YearsAtCompany`

**Problem.** `Copy of EOS Report.xlsx`'s "New" sheet computes tenure as an
exact day count — `D15 = D14-D13+1` (Last Working Day − Date of Joining +
1), `F15 = D15/365` — giving a value like `3.9452054794520546`. The
platform's Gratuity and Leave Balance calculators only ever read a supplied
`years_of_service`-pattern column (e.g. `YearsAtCompany`), which is
whatever precision the upload happens to provide (often pre-rounded, e.g.
`3.9`) — the platform never derived tenure from real hire/last-working-day
dates even when they were present in the upload.

**Fix.** [backend/core/labor_law_calculators.py](backend/core/labor_law_calculators.py):

1. Added three column-detection patterns, same local-regex convention as
   `contract_expiry_engine.py`'s `_CONTRACT_END_PATTERNS`/`_IQAMA_EXPIRY_PATTERNS`:
   `_HIRE_DATE_PATTERNS`, `_LAST_WORKING_DAY_PATTERNS`, and
   `_AS_OF_DATE_PATTERNS` (a fallback end-date signal for still-active
   employees who have no real separation date yet).
2. `_date_based_tenure_by_row(df, hire_col, end_col)` — exact replica of
   the Excel's `D15`/`F15` formula chain. Only rows where **both** dates
   parse get a value; nothing is guessed for a partial pair.
3. `_resolve_years_of_service(df, years_col, hire_col, end_col)` — merges
   the two tenure sources with the date-derived value winning **per row**
   whenever both dates parse; the `years_of_service` column is used only as
   a per-row fallback when no usable date pair exists for that employee.
   No rounding, business-day adjustment, or other interpretation was added
   beyond the Excel's own formula.
4. Wired into both `analyze_gratuity()` and `analyze_leave_balance()`:
   column detection, the "unavailable" gate (now satisfied by *either* a
   years column *or* both date columns), the row-level computation loop,
   new disclosure fields (`hire_date_column`, `last_working_day_column`,
   `n_tenure_computed_from_dates`), and narrative text (EN/AR) stating how
   many employees' tenure came from dates vs. the years column.
5. WPS Consistency was intentionally left untouched — the user's brief
   scoped Fix 2 to Gratuity and Leave Balance only.

**Re-verification against the reference scenario** (join 01/11/2022, last
day 10/10/2026, salary 10,425) — this session's already-Excel-matched
figures (`20,564.38` / `6,854.79` / `9,524.98`), now computed via the
date-based path with **no `YearsAtCompany` column supplied at all**:

```
$ POST /api/local/gratuity-calculator  (DateOfJoining=2022-11-01, LastWorkingDay=2026-10-10, MonthlySalary=10425)
  hire_date_column: DateOfJoining
  last_working_day_column: LastWorkingDay
  years_of_service_column: None
  n_tenure_computed_from_dates: 1
  years_of_service: 3.9452054794520546
  gratuity_full_award_sar: 20564.38     ✓ matches Excel I15 exactly
  gratuity_if_resignation_sar: 6854.79  ✓ matches Excel I13 exactly

$ POST /api/local/leave-balance-calculator  (same row, LeaveBalance=27.41)
  n_tenure_computed_from_dates: 1
  years_of_service: 3.9452054794520546
  compensation_sar: 9524.98             ✓ matches Excel E19 (9524.975) exactly
```

Identical to the figures already confirmed against the Excel earlier this
session — now derived purely from dates, confirming the date-based path
produces the same precision as the prior years-column path for this
scenario.

## Tests

Added 13 new tests to `tests/test_labor_law_calculators.py` (§7 — Phase 41:
date-based tenure): column-pattern detection for hire/last-working-day/
as-of-date columns; the exact reference-scenario reproduction for both
Gratuity and Leave Balance via dates only; the years-column fallback path
when no dates are present; per-row priority when both a years column and
dates are present (using a deliberately "wrong"/stale `YearsAtCompany`
value to prove the date-derived figure wins); the `AsOfDate` fallback for
still-active employees; unparseable-date exclusion (never guessed); and
`_to_dict()` serialization of the three new fields.

```
py -m pytest tests/test_labor_law_calculators.py -v
56 passed
```

## Regression suite

```
py -m pytest tests/ -q
1614 passed, 1 failed, 1 skipped
```

The one failure — `test_phase29_extended.py::TestCEODashboardVisualisations::test_health_wheel_imported`
— asserts `WorkforceHealthWheel` appears in `CEODashboard.tsx`, a file this
phase never touched. Confirmed via direct grep that the string is absent
from that file independent of any change here — a pre-existing gap
unrelated to this phase's scope, not a regression introduced by it.

## Live verification

- Screenshots: `SCREENSHOTS/phase28_gratuity_exact_precision.png`,
  `SCREENSHOTS/phase28_leave_exact_precision.png` — both captured against
  the running dev server with a fresh CSV containing only
  `DateOfJoining`/`LastWorkingDay` (no `YearsAtCompany` column), confirming
  exact 2-decimal SAR figures and the date-derived tenure narrative render
  correctly end-to-end through the actual UI.
- Direct API calls to `/api/local/gratuity-calculator` and
  `/api/local/leave-balance-calculator` reproduced the reference scenario
  exactly (see above).

## Note (not a change made)

The "Years" table column in both tabs displays `years_of_service` at full
raw precision (e.g. `3.9452054794520546`) — unformatted, matching how the
Excel itself carries full-precision `F15`. This wasn't in scope for either
requested fix (Fix 1 was SAR-only; Fix 2 explicitly required *not*
rounding the underlying tenure value), so it was left as-is. If a
shorter/rounded display for that one column is wanted, that's a follow-up
UI-only change, separate from either fix here.
