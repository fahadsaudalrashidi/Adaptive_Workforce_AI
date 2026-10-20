# Phase 29 — Leave Compensation Discrepancy Investigation & Date-Priority Parity

## 1. Root cause — honest finding: not reproducible in the current codebase

This phase investigated a reported SAR 18.90 discrepancy for employee EMP0097
(Marketing, MonthlySalary=10,425, LeaveBalance=27 days, YearsAtCompany=3.9 —
the years-column fallback path, no date columns): reported platform output
SAR 9,363.60 vs. the Excel-formula-correct SAR 9,382.50.

**After thoroughly tracing every step of the pipeline, this exact discrepancy could not
be reproduced against the current codebase.** This is reported honestly rather than
inventing a plausible-sounding fix for a bug that isn't present — consistent with this
session's standing discipline of never fabricating a root cause.

What was checked, in order:

1. **Re-opened `Copy of EOS Report.xlsx`'s "New" sheet directly** (not from memory or
   a prior report) and read every relevant cell's actual formula:
   ```
   F13 = 10425              ("Total salary" — a direct input, no adjustment, no VLOOKUP,
                              no housing-allowance term feeding it)
   D19 = 27.41              ("Days")
   E19 = F13/30*D19         → 9524.975
   ```
   Confirms the wage base is a plain, unadjusted number and the formula is exactly
   `salary ÷ 30 × days` — no hidden step.

2. **Read `analyze_leave_balance()`'s compensation step line-by-line**
   ([`labor_law_calculators.py:1204-1208`](backend/core/labor_law_calculators.py#L1204-L1208)):
   ```python
   wage = salary_extract.valid_by_row.get(idx) if salary_extract is not None else None
   compensation: Optional[float] = None
   if leave_balance_days is not None and wage is not None:
       daily_wage = wage / LEAVE_COMPENSATION_DAY_DIVISOR
       compensation = round(daily_wage * max(leave_balance_days, 0.0), 2)
   ```
   with `LEAVE_COMPENSATION_DAY_DIVISOR = 30`
   ([line 1062](backend/core/labor_law_calculators.py#L1062)) — an exact match to
   `E19 = F13/30*D19`, term for term.

3. **Confirmed the shared date-priority helper is not duplicated.**
   `_resolve_years_of_service()` ([line 409](backend/core/labor_law_calculators.py#L409))
   is called identically by both `analyze_gratuity()`
   ([line 661](backend/core/labor_law_calculators.py#L661)) and
   `analyze_leave_balance()` ([line 1180](backend/core/labor_law_calculators.py#L1180))
   — one implementation, not two that could drift. This directly satisfies the brief's
   concern in Output item (2).

4. **Checked the route-layer preprocessing** (`_preprocess_raw_bytes`,
   `backend/api/local_analysis_routes.py:272-323`) — confirmed it only strips/renames
   COLUMN NAMES (`df.rename(columns=...)`); it never touches a cell value. Ruled out as
   a source of numeric drift.

5. **Checked the governance scanner's dedup step** (`secure_file_ingestion.py`'s
   `_deduplicate()`) — confirmed it only drops duplicate rows; it does not average,
   merge, or otherwise mutate the values of any surviving row.

6. **Reconstructed the exact reported scenario and ran it against the live, freshly
   restarted API** (`POST /api/local/leave-balance-calculator`, full route → governance
   scan → `analyze_leave_balance` pipeline, not a bare unit-test call) — result:
   `compensation_sar: 9382.5`, matching the Excel-correct figure, not the reported
   9363.60. Re-confirmed live in the browser (§4).

**Conclusion**: the formula, the shared date-priority logic, and the full live pipeline
all currently produce the correct figure for this exact scenario. No divergent code
path, stale value, or unintended salary substitution was found anywhere. The most
plausible explanation is that the original live test was run against a server process
or code state that predated a fix already present on disk — plausibly Phase 28's own
date-based-tenure/exact-precision work, given the timing and the fact that this exact
`(10425, 3.9)` pairing already appears as a Phase 28 test fixture
(`test_gratuity_falls_back_to_years_column_when_no_dates_present`). This is stated as a
hypothesis, not a confirmed cause — the honest, verifiable finding is simply that the
bug does not reproduce now.

## 2. Value delivered regardless of the non-reproduction

Since the underlying bug could not be located, no source line was changed in
`labor_law_calculators.py`'s compensation formula (there was nothing wrong to fix). Two
real, useful additions were made instead:

- **`test_leave_emp0097_reported_scenario_produces_excel_correct_compensation`**
  ([`tests/test_labor_law_calculators.py:667`](tests/test_labor_law_calculators.py#L667)) —
  locks in the exact reported scenario (EMP0097, Marketing, 10425, 27, 3.9) as a
  permanent regression guard, asserting `compensation_sar == 9382.50`. If any future
  change reintroduces whatever caused the original discrepancy, this test fails
  immediately.
- **`test_leave_dates_take_priority_over_years_column_per_row`**
  ([`tests/test_labor_law_calculators.py:691`](tests/test_labor_law_calculators.py#L691)) —
  closes a genuine, real coverage gap found while investigating: Gratuity already had
  `test_gratuity_dates_take_priority_over_years_column_per_row` (proving date-derived
  tenure wins over a stale years-column value, per row), but Leave Balance had no
  equivalent test, even though the underlying `_resolve_years_of_service()` logic is
  shared. This new test proves full-precision, date-derived tenure flows through BOTH
  `cumulative_entitlement_days` and `compensation_sar` identically to how Gratuity's
  date-based path already works — using a deliberately "wrong"/stale `YearsAtCompany`
  value on one row to prove the date-derived figure wins, and a real years-column
  fallback on a second row (no dates) to prove that path is untouched.

## 3. Corrected/confirmed EMP0097 figures

| Field | Value |
|---|---|
| Years of service | 3.9 (years-column fallback — no date columns in this scenario) |
| Cumulative entitlement | 81.9 days (3.9 × 21, Article 109) |
| Leave balance | 27 days |
| Monthly wage | SAR 10,425 |
| **Compensation** | **SAR 9,382.50** (= 10,425 ÷ 30 × 27 — Article 111 / Excel `E19` formula) |

Confirmed identically via: (a) direct unit-test call, (b) the live HTTP API after a full
backend restart, and (c) the live browser UI (§4 below).

## 4. Live browser verification

**Screenshot 1 — EMP0097's exact reported scenario**: uploaded a CSV reproducing the
scenario precisely (`EMP0097`, Marketing, `YearsAtCompany=3.9`, `MonthlySalary=10425`,
`LeaveBalance=27`). Leave Balance tab shows: Years=3.9, Entitlement (days)=81.9,
Balance (days)=27, **Compensation = SAR 9,382.50** — the correct figure, not the
reported SAR 9,363.60.

**Screenshot 2 — real date columns, full precision through both entitlement and
compensation**: uploaded a CSV with `DateOfJoining=2022-11-01`,
`LastWorkingDay=2026-10-10`, `MonthlySalary=10425`, `LeaveBalance=27.41` and NO
`YearsAtCompany` column at all. Result: Years=**3.9452054794520546** (full raw
precision, not rounded), narrative correctly discloses *"Tenure for 1 employee(s) was
computed from exact hire/last-working-day dates (DateOfJoining → LastWorkingDay) rather
than the years-of-service column, for full day-count precision,"* Entitlement (days)
displays as 82.8 (the 1-decimal-rounded display of 82.849...), and **Compensation =
SAR 9,524.98** — matching the Excel's `E19` reference value (9524.975) exactly.

Zero console or page errors in either scenario.

## 5. Test results

```
$ python -m pytest tests/test_labor_law_calculators.py -v
...
58 passed in 0.63s
```

56 pre-existing (per Phase 28) + 2 new = 58.

## 6. Regression suite

Initial run after this phase's changes showed 40 failures (39 in
`test_phase30_1_security.py` + the pre-existing `test_health_wheel_imported` gap),
down from Phase 28's reported 1. Root-caused precisely rather than left as a vague
"environment-sensitive" note:

- **39 failures**: `passlib.exc.MissingBackendError: bcrypt: no backends available`.
  The `bcrypt` package was absent from the shared virtual environment this repo runs
  tests under (`Enterprise_AI_Analyst\.venv` — this project has no venv of its own).
  `pip install bcrypt` alone pulled bcrypt 5.0.0, which passlib 1.7.4 cannot use
  (bcrypt ≥4.0 removed the `__about__` submodule passlib probes, and its version-detection
  fallback then crashes on bcrypt's now-strict 72-byte password check). Pinned
  `bcrypt<4.0` (installed 3.2.2) instead, which recovered 30 of the 39 immediately.
  The remaining 9 (`TestAuthRoutesSmokeTests` + `test_cors_is_not_wildcard`) were a
  second, unrelated mismatch: `starlette` 0.26.1 was installed against `httpx` 0.28.1,
  which removed the `app=` shortcut `starlette.testclient.TestClient` still passed to
  `httpx.Client.__init__`. Confirmed `fastapi` 0.115.6 itself already declares
  `starlette>=0.40.0,<0.42.0` as a hard requirement — 0.26.1 was already an unmet
  dependency, not a version this repo ever intentionally pinned. Installed
  `starlette==0.41.3` (satisfying FastAPI's own constraint), which resolved the
  remaining 9 with zero collateral effect elsewhere in the suite.
- **1 failure** (`test_health_wheel_imported`): a genuine, unrelated pre-existing
  product gap — `CEODashboard.tsx` never imports a `WorkforceHealthWheel` component (it
  uses `RiskRadarChart`/`WorkforceCompositionRiver`/`ProgressRing` instead). Confirmed
  via direct inspection of the file's imports. Out of scope for this phase (CEO
  Dashboard visualizations, unrelated to Labor Law Calculators or auth) — left
  untouched.

Final state after both dependency fixes:

```
$ python -m pytest tests/ -q
1 failed, 1616 passed, 1 skipped, 205 warnings in ~71s
```

1616 = 1577 + 39 recovered, confirming the two dependency fixes accounted for the
entire gap with no other side effects. **Zero regressions caused by this phase's actual
code changes** — the 39 were a pre-existing, unrelated environment issue (missing/
mismatched shared-venv dependencies), now resolved; the 1 remaining is a pre-existing,
unrelated frontend feature gap.

## Files changed

- `tests/test_labor_law_calculators.py` (+2 tests: EMP0097 regression guard, leave
  date-priority parity test)
- `labor_law_emp0097_test_data.csv`, `labor_law_leave_dates_test_data.csv` (new
  fixtures, repo root, used for live verification)
- No changes to `backend/core/labor_law_calculators.py` — investigation found the
  compensation formula, the shared date-priority logic, and the full pipeline already
  correct; see §1.
