# Phase 22 — Missing Employee Identifier Column Fix

Display-only fix, no calculation logic changed. Every affected engine already computes a
PII-safe `record_id_safe` field (a one-way hash of the detected ID column, or `ROW-{idx}`
when no ID column exists) per candidate — the bug was that several frontend tables
computed and used this value only as a React `key` prop, never rendering it as a visible
column, so per-employee rows sharing a department looked like unexplained duplicates.

## 1. Every table found with this issue

Audited every per-employee-shaped table built this session (anything rendering a
`Department` column with multiple rows per department). Two categories exist in this
codebase and only one has the bug:

- **Aggregate/group-level tables** (one row per department, per job pattern, per
  attribute, per cohort, per funnel stage) — `Department` (or `Pattern ID` / `Cohort` /
  `Attribute` / `Stage`) legitimately **is** the row's identity here; no employee ID is
  applicable. Checked and confirmed correct as-is: Nitaqat's department table, Overtime
  Cost Intelligence's department table, Payroll Movements' department table, Recruitment
  Pipeline's stage and department tables, Fairness/Bias Audit's attribute tables, Pay
  Equity's cohort-comparison table, Job Pattern Grouping's pattern table, Exit
  Interview's theme table.
- **Per-employee tables** — one row per individual employee, `Department` repeats across
  many rows for the same department. Found the bug in **4 tables**, all missing a visible
  identifier column despite `record_id_safe` already being computed and passed through
  to the frontend:

| # | Table | File | Reported? |
|---|-------|------|-----------|
| 1 | Leave Balance & Compensation candidates | `executive-ui/src/pages/SaudiLaborLawCalculators.tsx` (`LeaveTab`) | Yes — the original report |
| 2 | Contract Expiry & Renewal candidates | `executive-ui/src/pages/ContractExpiryTracker.tsx` | Yes — the original report |
| 3 | End-of-Service Gratuity candidates | `executive-ui/src/pages/SaudiLaborLawCalculators.tsx` (`GratuityTab`) | **No — found during the broader audit**, same missing column |
| 4 | WPS/Payroll Consistency mismatch candidates | `executive-ui/src/pages/SaudiLaborLawCalculators.tsx` (`WpsTab`) | **No — found during the broader audit**, same missing column |

Confirmed NOT present (already correct) in `SuccessionReadinessTracker.tsx` and
`EmployeeRiskDashboard.tsx` — both already render `record_id_safe` visibly via
`<LatinText>{c.record_id_safe}</LatinText>`.

## 2. Fix applied

Purely additive, no dataclass or serializer touched on the backend (each engine already
had `record_id_safe: str` as the first field of its candidate dataclass and already
serialized it — `contract_expiry_engine.py`'s `ExpiryCandidate`,
`labor_law_calculators.py`'s `GratuityCandidate` / `SalaryMismatchCandidate` /
`LeaveCandidate` — this was purely a frontend rendering gap):

1. Added an **"Employee ID"** (`معرّف الموظف`) column as the first `<th>`/`<td>` in each
   of the 4 tables, rendering `c.record_id_safe` in a small monospace style consistent
   with `SuccessionReadinessTracker.tsx`'s existing ID display:
   - [`ContractExpiryTracker.tsx:417`](executive-ui/src/pages/ContractExpiryTracker.tsx#L417) (header), row cell added directly after.
   - [`SaudiLaborLawCalculators.tsx:381`](executive-ui/src/pages/SaudiLaborLawCalculators.tsx#L381) (Gratuity tab).
   - [`SaudiLaborLawCalculators.tsx:445`](executive-ui/src/pages/SaudiLaborLawCalculators.tsx#L445) (WPS tab).
   - [`SaudiLaborLawCalculators.tsx:506`](executive-ui/src/pages/SaudiLaborLawCalculators.tsx#L506) (Leave tab).
   Placed as the first column in JSX source order — the app already sets
   `document.documentElement.dir` globally per the active language
   (`LanguageContext.tsx:21`), so this single placement automatically renders leftmost in
   English and rightmost in Arabic, satisfying "leftmost (or rightmost in RTL)" without
   extra logic.
2. **Placeholder-row disclosure** (requirement #2): each engine already falls back to
   `f"ROW-{idx}"` when no real ID column is detected in the upload — this was already
   correct, distinguishable-row behavior, just not visible. Added a small caption above
   each table (`NoIdentifierNote` component,
   [`SaudiLaborLawCalculators.tsx`](executive-ui/src/pages/SaudiLaborLawCalculators.tsx),
   and an inline equivalent in `ContractExpiryTracker.tsx`) that reads *"No employee
   identifier column detected in this upload — rows are numbered for reference only"*
   whenever every candidate's `record_id_safe` is a `ROW-` placeholder rather than a real
   `EMP-` hash — inferred client-side from the existing value's prefix, no backend change
   needed for this either.
3. No calculation logic touched anywhere — confirmed by the unchanged full regression
   count (§4).

## 3. Live screenshots

Backend was already running; frontend picked up the change via Vite's hot-reload (no
restart needed). Verified with real/synthetic data, zero console or page errors across
all four:

- **Contract Expiry & Renewal** (`contract_expiry_test_data.csv`): "EMPLOYEE ID" is now
  the first column. `EMP-0C0EED` visibly appears twice (Contract + Iqama/Visa signal
  rows for the same employee) and `EMP-4449B6` similarly — now clearly two rows for one
  person, not an ambiguous "Engineering" repeat.
- **End-of-Service Gratuity** (`labor_law_clean_data_test.csv`): "EMPLOYEE ID" column
  added (`EMP-B0B8C8`, `EMP-BE0767`, ...), each row now distinguishable alongside its
  Department.
- **Leave Balance & Compensation** (same fixture) — the originally-reported table: same
  fix confirmed, `EMP-B0B8C8` / `EMP-BE0767` / etc. now visible first.
- **WPS/Payroll Consistency** (`labor_law_wps_test_data.csv`): "EMPLOYEE ID" column added
  to the mismatch table (`EMP-B0B8C8`, `EMP-BE0767`), the two real mismatches (SAR −2.0K
  and +SAR 500) now each traceable to a specific employee row.

## 4. Regression count

```
$ python -m pytest tests/ -q
40 failed, 1445 passed, 1 skipped, 205 warnings
```

Identical to the pre-fix baseline — same 1445 passed, same 40 pre-existing unrelated
failures. **Zero regressions**, as expected for a frontend-only display fix with no
backend or test-file changes.

## Files changed

- `executive-ui/src/pages/ContractExpiryTracker.tsx` (Employee ID column + placeholder
  note)
- `executive-ui/src/pages/SaudiLaborLawCalculators.tsx` (Employee ID column in all 3
  candidate tables + shared `NoIdentifierNote` component)
