# Payroll Movements Dedup Fix — Composite (Employee, Period) Key

Status: **Fixed, tested, live-verified. Zero regressions.**

---

## 1. Bug, exact location

`backend/core/secure_file_ingestion.py:466-476` (pre-fix) — `_deduplicate()`'s
ID-based branch matched on `subset=[id_col]` alone whenever a confident
employee-ID column was detected, with no awareness of a period/date column.
For longitudinal data (the same `EmployeeID` legitimately repeating once per
period), every row after the first for each employee was flagged and
dropped as a "duplicate."

**Reproduced directly** before any fix, using the exact shape from the bug
report (60 employees × 18 periods = 1,080 rows):

```
total rows built: 1080
deduped rows: 60
notes: ["1020 duplicate row(s) removed before analysis (matched by 'EmployeeID'
— the same ID appeared more than once). 1080 row(s) in the original upload,
60 remain."]
```

Matches the reported symptom exactly (1020 removed, 60 remain), then
`payroll_movement_tracker.analyze_payroll_movements()` correctly-but-uselessly
reported `available: False` since only single-snapshot data remained.

Call path confirmed: `local_analysis_routes.py`'s `/payroll-movements` route
→ `_scanner.scan(...)` → `SecureFileIngestion._deduplicate()`
(`secure_file_ingestion.py:228`) — the **same shared scanner instance**
(`_scanner`) used by every other route (Overtime, Fairness, Nitaqat,
Succession, etc.), confirming the fix has to live in the shared dedup
function itself, scoped narrowly by column detection, not duplicated
per-route.

---

## 2. Fix

`backend/core/secure_file_ingestion.py:123-134` — new `_PERIOD_COLUMN_PATTERNS`,
**intentionally the same regex** as `payroll_movement_tracker.py`'s own
`_PERIOD_PATTERNS` (`payroll_movement_tracker.py:57-60`), kept as a local
copy rather than a shared import — this codebase has no existing convention
of one module importing another's column-detection patterns (each engine
keeps its own locally, e.g. `_ID_COLUMN_PATTERNS`-style tuples in
`succession_readiness_engine.py`, `nitaqat_compliance_engine.py`, etc.), and
pipeline-level dedup runs *before* any engine ever sees the dataframe, so it
can't import the payroll engine without inventing a new
dedup-depends-on-engine dependency that doesn't exist anywhere else.

`secure_file_ingestion.py:443-509` — `_deduplicate()` now branches three ways:

1. **ID column + period column both detected** (new): composite-key dedup —
   `df.duplicated(subset=[id_col, period_col], keep="first")`
   (`secure_file_ingestion.py:489`). Two rows are duplicates only when both
   the ID *and* the period match. Disclosure message:
   `"N duplicate (employee, period) row(s) removed... matched by 'EmployeeID'
   + 'Period' together... the same employee across different periods is
   legitimate longitudinal data and was kept."`
2. **ID column only, no period column** (unchanged): byte-for-byte the
   original ID-only behavior and message text
   (`secure_file_ingestion.py:503-510`).
3. **No ID column** (unchanged): full-row match fallback, untouched.

Scoping check performed *before* writing the fix, not after: grepped every
CSV fixture in the repo (`test_employee_data.csv`, `messy_test_data.csv`,
`nitaqat_test_data.csv`, `succession_test_data.csv`,
`messy_recruitment_data.csv`) plus every relevant test file's inline
DataFrame fixtures (Overtime, Fairness, Nitaqat, Succession, Employee Risk)
against `_PERIOD_COLUMN_PATTERNS` — **none** have both an ID column and a
period-matching column, so none of them change behavior. (One near-miss
checked explicitly: `messy_recruitment_data.csv`'s `ApplicationDate`/
`HireDate` do **not** match — `\bdate\b` requires a word boundary before
"date," and both column names glue it directly onto a preceding letter with
no boundary, so this was already true of the payroll engine's own detection
before this fix, not something the fix changed.)

Verified the fix directly:

```
total rows built: 1080
deduped rows: 1080          # was 60 pre-fix
notes: []                    # zero false-positive removals

with 1 genuine dup injected -> deduped rows: 1080
notes2: ["1 duplicate (employee, period) row(s) removed before analysis
(matched by 'EmployeeID' + 'Period' together — the same employee AND the
same period both appeared more than once; the same employee across
different periods is legitimate longitudinal data and was kept). 1081
row(s) in the original upload, 1080 remain."]
```

---

## 3. Tests

`tests/test_duplicate_row_deduplication_phase35_5.py` — new class
`TestDeduplicateCompositeKeyForLongitudinalData`, 6 tests, all passing:

| Test | Asserts |
|---|---|
| `test_same_employee_across_many_legitimate_periods_is_not_stripped` | 60×18 = 1,080-row fixture → all 1,080 kept, zero notes |
| `test_actual_duplicate_same_employee_same_period_is_removed` | Genuine (id, period) duplicate injected → exactly 1 removed |
| `test_composite_dedup_disclosure_names_both_matched_columns` | Disclosure message names both `EmployeeID` and `Period`, states the "kept" reasoning |
| `test_no_period_column_still_uses_id_only_dedup` | ID-only dedup message/behavior unchanged when no period column present |
| `test_full_scan_end_to_end_preserves_multi_period_row_count` | Full `scan()` pipeline (not just `_deduplicate()`) → `row_count == 1080` |
| `test_full_scan_end_to_end_removes_genuine_period_duplicate_only` | Full pipeline correctly reports the 1-row composite removal |

```
py -m pytest tests/test_duplicate_row_deduplication_phase35_5.py -v
16 passed   (10 pre-existing + 6 new, zero regressions in this file)
```

---

## 4. Full regression suite

```
Before this fix (Phase 8 baseline): 39 failed, 1346 passed, 1 skipped
After this fix:                     39 failed, 1352 passed, 1 skipped

py -m pytest tests/ -q --ignore=tests/test_phase30_1_security.py
  1333 passed, 1 skipped, 0 failed   (was 1327 — +6 new tests)
```

The 39 failures are the same pre-existing, unrelated `passlib`/bcrypt
`MissingBackendError` in `test_phase30_1_security.py` present since Phase 5
(confirmed unchanged in count across Phases 5→9). **Zero regressions**:
every Overtime/Fairness/Nitaqat/Succession/Recruitment/Employee-Risk test
that exercises dedup still passes unchanged, confirming those modules'
one-row-per-employee dedup behavior is byte-for-byte preserved.

---

## 5. Live browser verification

Backend restarted (`python backend/api/main.py`, not `--reload`, so a
restart was required to pick up the code change — confirmed via a direct
`curl` to `/api/local/payroll-movements` before opening the browser, which
returned `row_count: 1080, available: true, data_mode: "longitudinal",
n_employees_total: 60, n_periods_detected: 18`).

New fixture: `payroll_longitudinal_test_data.csv` — 60 employees × 18
periods (`2024-01`...`2025-06`), columns `EmployeeID`, `Period`,
`Department`, `MonthlyIncome`, with a gradual per-period raise drift so the
Payroll engine has a real hike signal to report (not a flat line).

Playwright, against the live dev server, console errors: **`[]`**.
Uploaded `payroll_longitudinal_test_data.csv` to the Payroll Movements
Tracker page:

- `payroll_longitudinal_test_data.csv · 1,080 rows` (not 60 — the fixed
  ingestion count)
- Green **"Longitudinal — real period-over-period history"** badge (was
  previously the "not available" fallback for this same shape of data)
- KPIs: `Average Movement +0.1%`, `Employees Covered 60`,
  `Periods Detected 18`
- Full department breakdown table (Sales, Operations, Finance, Engineering)

Screenshot: `payroll_longitudinal_fixed.png`.

---

## 6. Files changed

| File | Change |
|---|---|
| `backend/core/secure_file_ingestion.py` | New `_PERIOD_COLUMN_PATTERNS` (`:123-134`). `_deduplicate()` composite-key branch (`:443-509`). |
| `tests/test_duplicate_row_deduplication_phase35_5.py` | +6 tests, new `TestDeduplicateCompositeKeyForLongitudinalData` class + `_longitudinal_payroll_df()` helper. |
| `payroll_longitudinal_test_data.csv` | **New** fixture (60 employees × 18 periods, 1,080 rows). |
