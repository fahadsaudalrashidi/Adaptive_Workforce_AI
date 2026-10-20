# Phase 35.5 Corrections Report — Fixes from Live Messy-Data Testing

Date: 2026-08-06
Scope: two confirmed bugs found via live browser testing with a deliberately messy 17-row CSV (mixed Arabic/English department casing, an exact duplicate row), plus verification of where Phase 4 sector benchmarking is actually reachable in the live UI. Follows on from `PHASE_4_MODULES_REPORT.md`.

**Verification method for every claim below:** direct code inspection (file:line citations), a dedicated pytest file per bug (26 new tests, all real computed-value assertions using the exact reported fixture cases — Sales/مبيعات, Finance/finance, an EMP001 duplicate row), a full regression run of the pre-existing suite before and after, and a live Playwright browser session against the actual running backend + Vite dev server with a deliberately messy 61-row test CSV, screenshots taken, console errors checked.

**Explicitly not touched, per instruction:** Payroll Movements' "single snapshot" disclosure and Exit Interview's "0 themes, insufficient respondents" behavior — both already correct, left alone.

**Addendum (same date):** live re-testing after the fixes below shipped surfaced a regression — see §5 — a `TypeError: 'float' object is not iterable` crash on both pages, caused by the new `department_normalizer.py` itself. Fixed and re-verified; see §5 for the full trace.

---

## 1. Bug 1 — Department names not normalized before grouping

### Root cause

Three independent modules grouped employee records by department using raw string equality (`groupby()` / dict keys on the untouched column value). `"Sales"`, `"مبيعات"` (Arabic for Sales), `"Finance"`, and `"finance"` were therefore treated as four distinct departments instead of two, corrupting every downstream at-risk percentage, department-level cost figure, and risk cross-reference computed from that grouping. Confirmed systemic (not a one-off) by inspecting all three call sites directly:

| File | Grouping call site (pre-fix) |
|---|---|
| `backend/core/employee_risk_scoring.py` | `_build_group_summary()`, `groups.setdefault(key, []).append(rec)` on raw `department`/`specialty` values — this is the ROOT `department_summary` source almost every other module reads |
| `backend/core/overtime_cost_intelligence_engine.py` | `work.groupby("_dept")` on `df[dept_col].astype(str)`, unnormalized |
| `backend/core/payroll_movement_tracker.py` | **two** separate grouping code paths, both unnormalized: `_analyze_longitudinal()`'s `moves.groupby("_dept")` and `_analyze_snapshot_proxy()`'s `work.groupby("_dept")` |

Existing bilingual-mapping code was checked for reuse first, per instruction (`saudi_schema_intelligence.py`, `theory_aware_column_mapper.py`, `risk_intelligence.py`'s `DEPT_SYNONYMS`) — all of it maps **column names** (e.g. matching a header like "القسم" to "department"), not department **values**. None solved this problem, so a new module was justified.

### Fix location

**New file: `backend/core/department_normalizer.py`** — the single canonical department-value normalizer, used by all three call sites. Two tiers, both auditable:

1. **Exact normalization** (always applied, not disclosed — no genuine ambiguity): whitespace trim + casefold. `"Finance" == "finance" == " Finance "`.
2. **Curated EN/AR synonym table** (`EN_AR_DEPARTMENT_SYNONYMS`, 20 entries covering common Saudi/GCC department names) — applied and **disclosed** via `DepartmentNormalizationResult.merges_applied`, e.g. `"Sales"` ↔ `"مبيعات"`.

Explicitly **not** attempted: cross-script (Arabic vs. Latin) fuzzy similarity matching — string-similarity algorithms are not meaningful between scripts sharing no characters. Same-script near-duplicates (e.g. "Marketing" vs "Marketting") ARE flagged via `difflib.SequenceMatcher` (threshold 0.82) as `unmerged_similar_variants` for human review, never auto-merged.

**Call sites updated:**

| File | Change | Evidence |
|---|---|---|
| `backend/core/employee_risk_scoring.py` | `_build_group_summary()` (`:875`) now calls `normalize_department_series(raw_values)` (`:895`) and returns `(summaries, disclosure_warnings)` instead of just `summaries` (`:1018`); disclosure strings extended into the result's top-level `warnings` list |
| `backend/core/overtime_cost_intelligence_engine.py` | `analyze_overtime_cost_intelligence()` (`:208`) calls `normalize_department_series(df[dept_col].astype(str))` (`:308`); new `department_normalization_notes: list[str]` field added to `OvertimeCostIntelligenceResult` and its `to_dict()` |
| `backend/core/payroll_movement_tracker.py` | Both `_analyze_longitudinal()` (`:240`) and `_analyze_snapshot_proxy()` (`:345`) call `normalize_department_series(work["_dept"])` (`:256`, `:382`); same new `department_normalization_notes` field added to `PayrollMovementResult` and its `to_dict()` |

### Tests

`tests/test_department_normalization_phase35_5.py` — **12 new tests**, using the exact reported fixture (`Sales`, `مبيعات`, `Finance`, `finance`, `Operations `, `Operations`, `Sales`, `Engineering`) against `department_normalizer.py` directly and against all three consuming modules end-to-end. Confirms the fixture collapses from 8 raw values to the correct 4 departments (`Sales:3, Finance:2, Operations:2, Engineering:1`) in every module, and that every merge is disclosed in `warnings`/`department_normalization_notes`, never silent. Also confirms two genuinely different, unlisted department names are **not** merged (`test_unrelated_unlisted_departments_are_not_merged`).

### Live verification (before/after)

Uploaded a 61-row test CSV (`messy_test_data.csv`, generated for this test — 10 rows each of `Sales`/`مبيعات`/`Finance`/`finance`/`"Operations "`/`Operations`, plus 1 exact duplicate row) to the **Overtime Cost Intelligence** and **Payroll Movements** pages via a live Playwright browser session against the actual running backend + Vite dev server.

**Before the fix** (reproduced directly against the pre-fix grouping logic): 6 separate department rows — `Sales`, `مبيعات`, `Finance`, `finance`, `"Operations "`, `Operations` — each undercounted.

**After the fix, live in the browser, both pages:**

| Department | Employees |
|---|---|
| Sales | 20 |
| Finance | 20 |
| Operations | 20 |

...with a visible blue "Department names normalized" disclosure box on both pages listing every merge:
```
· Merged 'Sales', 'مبيعات' into 'Sales' (recognised as the same department): {'Sales': 10, 'مبيعات': 10}.
· Merged 'Finance', 'finance' into 'Finance' (recognised as the same department): {'Finance': 10, 'finance': 10}.
· Merged 'Operations', 'Operations ' into 'Operations' (recognised as the same department): {'Operations ': 10, 'Operations': 10}.
```
Zero console errors on either page. Frontend changes: `executive-ui/src/pages/OvertimeCostIntelligence.tsx` and `executive-ui/src/pages/PayrollMovementsTracker.tsx` both updated to render `department_normalization_notes` (new interface field + disclosure `<div>`), since the backend already computed this disclosure but no page previously displayed it.

---

## 2. Bug 2 — Duplicate rows not deduplicated

### Root cause

`SecureFileIngestion._compute_data_quality()` (`backend/core/secure_file_ingestion.py`) already **counted** duplicate rows (`duplicate_rows = int(df.duplicated().sum())`) and generated a warning ("N duplicate row(s) detected... These may skew model training") — but never actually **removed** them. The raw, un-deduplicated dataframe (`result.df`, exposed downstream as `ir.df`) flowed unchanged into every consuming module (`EmployeeRiskScorer.score_dataframe`, `analyze_overtime_cost_intelligence`, `analyze_payroll_movements` — confirmed via `backend/api/local_analysis_routes.py:1382,1393,1497,1508`, all three passed `ir.df` directly). A duplicated at-risk employee (identical `EmployeeID`, identical row) was therefore counted twice, inflating that department's at-risk percentage (e.g. Sales showing 2/3 = 67% instead of the correct 1/2 = 50%).

### Fix location

**`backend/core/secure_file_ingestion.py`** — new `_deduplicate()` method (`:424`), called once inside `scan()` (`:223`) immediately after ingestion, **before** column classification or data-quality scoring — so every downstream caller of `SecureFileIngestion.scan()` (risk scoring, overtime cost, payroll movements) gets the deduplicated dataframe automatically, without needing a per-module fix.

Strategy (pipeline-level, per instruction):
- If a confident employee-ID column exists (`_ID_COLUMN_PATTERNS` — `employee_id`/`emp_id`/`staff_id`/etc.), dedupe on that column, keep first occurrence: two rows sharing the same employee ID are the same person regardless of what else differs.
- Otherwise, dedupe on exact full-row match only — a partial overlap between two rows is never assumed to be the same record.
- **Never silent:** every removal returns a disclosure string (e.g. `"1 duplicate row(s) removed before analysis (matched by 'EmployeeID' — the same employee ID appeared more than once). 61 row(s) in the original upload, 60 remain."`) appended to `report.warnings`; `result.df`/`result.row_count` are updated to the deduplicated dataframe/count.

The old count-only warning branch (`if dq.duplicate_rows > 0: warnings.append(...)`) and the matching "De-duplicate N rows" recommendation were removed as dead code — `_compute_data_quality()` now runs on the already-deduplicated dataframe, so `duplicate_rows` is always 0 by the time it's computed; the new `_deduplicate()` disclosure supersedes it with a more specific message.

**`backend/api/local_analysis_routes.py`** (`:1408`, `:1524`) — added `"data_quality_warnings": report.warnings` to both the `/api/local/overtime-cost-intelligence` and `/api/local/payroll-movements` JSON responses. This field did not exist before; the duplicate-row disclosure computed by the backend was reaching neither page.

**Frontend:** `executive-ui/src/pages/OvertimeCostIntelligence.tsx` and `executive-ui/src/pages/PayrollMovementsTracker.tsx` — new `data_quality_warnings` interface field, and an amber disclosure box (filtered to warnings containing `"duplicate row"`) rendered directly under the filename/row-count header, above the KPI cards.

### Tests

`tests/test_duplicate_row_deduplication_phase35_5.py` — **10 new tests**, using the exact reported EMP001 case (identical `EmployeeID`, identical row, duplicated). Covers: ID-based dedup, full-row-match fallback when no ID column exists, that a partial (non-exact) row overlap without an ID column is correctly *not* merged, that two genuinely different employees who happen to share non-ID field values are correctly *not* merged, that the disclosure is never silent (`report.warnings` always contains the removal note when rows are removed), and a direct regression proof that a duplicated at-risk employee no longer inflates a department's record count (`TestDuplicateRowAtRiskPercentageFix`).

### Live verification (before/after)

Same 61-row messy CSV as Bug 1 (which also contains one exact `EMP001`-style duplicate row) uploaded to both pages.

**Before the fix:** 61 rows would have been analyzed, with the duplicated employee counted twice in its department's totals.

**After the fix, live in the browser, both pages** — filename line now reads `messy_test_data.csv · 60 rows` (not 61), with a visible amber disclosure box directly beneath it:

> ⚠ 1 duplicate row(s) removed before analysis (matched by 'EmployeeID' — the same employee ID appeared more than once). 61 row(s) in the original upload, 60 remain.

Zero console errors.

---

## 3. Sector Benchmarking (Phase 4) — confirmed live UI location

### Investigation

Searched the entire `executive-ui/src` tree for any reference to `salary_benchmark_confidence`, `employment_sector`, `GASTAT`, or `EMPLOYMENT_SECTOR_BENCHMARK_CONFIDENCE` — **zero matches**. The "sector" content the user found under **مركز القرار (Decision Center)** is `executive-ui/src/components/visualizations/BenchmarkGapPanel.tsx` — a **different, Phase 29F feature**: an industry-vertical (banking/oil_gas/telecom/government/retail_fmcg/healthcare) benchmark-gap comparison with k-anonymity ≥5 and differential-privacy noise (ε=0.5), unrelated to `financial_intelligence_engine.py`'s GASTAT employment-sector model.

Searched the backend for every consumer of `financial_intelligence_engine.py`: it's imported by `executive_roi_engine.py` and the three report exporters (`executive_pdf_exporter.py`, `executive_pptx_exporter.py`, `executive_slide_exporter.py`) — all of which produce **downloadable PDF/PPTX/slide artifacts**, not live pages — plus `overtime_cost_intelligence_engine.py`, which is the **only** module that both imports from `financial_intelligence_engine.py` *and* backs a live page. But before this correction, it only called `estimate_monthly_salary("diversified", "mid")` — the uncalibrated fallback, with no `employment_sector` argument and no `salary_benchmark_confidence` field on its result at all.

**Confirmed: Phase 4 sector-benchmark output was genuinely unreachable from any live page.** Per instruction (no new page, no new report generator), it has been wired into the existing **Overtime Cost Intelligence** page — the one live page already positioned for it.

### Fix

**`backend/core/overtime_cost_intelligence_engine.py`**:
- Imports `infer_employment_sector_from_metadata` and `salary_benchmark_confidence_for` from `financial_intelligence_engine.py` (`:55-56`).
- `analyze_overtime_cost_intelligence()` now calls `infer_employment_sector_from_metadata(department_summary)` (`:270`) and threads the result into `estimate_monthly_salary(..., employment_sector=employment_sector)` (`:274`, `:280`) whenever the real salary column is missing or has gaps, using the real GASTAT-cited table when a sector signal exists in department metadata instead of the uncalibrated industry-vertical guess.
- New `salary_benchmark_confidence: str` and `employment_sector_used: Optional[str]` fields added to `OvertimeCostIntelligenceResult` (`:284` computes the value) and its `to_dict()` — one of `"observed"` (real salary column present), `"gastat_official_2018"` (real GASTAT data, sector inferred), or `"uncalibrated_generic_estimate"` (last-resort industry guess, honestly labeled).

**Frontend (`executive-ui/src/pages/OvertimeCostIntelligence.tsx`):** new "SALARY BENCHMARK" badge, always visible (not just when estimated), showing the confidence label in plain English/Arabic (`"Observed (from your data)"` / `"GASTAT Official 2018"` / `"Uncalibrated generic estimate"`) plus the inferred sector when applicable.

### Tests

Appended to `tests/test_overtime_cost_intelligence_engine.py` — **4 new tests** covering all three confidence tiers (`observed` when a real salary column exists; `uncalibrated_generic_estimate` when no salary column and no sector signal; `gastat_official_2018` when department metadata implies a government employer, e.g. "Ministry of Finance"; and that both new fields serialize correctly).

### Live verification

Same 61-row messy CSV (has a real `MonthlyIncome` column) uploaded to the Overtime Cost Intelligence page. The "SALARY BENCHMARK" row is visibly rendered between the KPI cards and the narrative:

> SALARY BENCHMARK &nbsp; **Observed (from your data)**

— confirming the confidence label is shown to the user directly on the page, not just present in the API payload. (A dataset without a salary column, tested via direct backend call, correctly shows `gastat_official_2018` when department metadata implies a government employer, and `uncalibrated_generic_estimate` otherwise — both paths test-covered above.)

---

## 5. Regression — `TypeError: 'float' object is not iterable` (found in live re-testing)

### Root cause

`backend/core/department_normalizer.py:171` (pre-fix) built the per-row raw-value series as `raw_str = raw.astype(str)`, on the assumption that `pandas.Series.astype(str)` always stringifies every value, including `NaN`/`None`. **That assumption is false on this project's pandas version (3.0.3):** confirmed directly —

```python
>>> pd.Series(['Sales', None, np.nan]).astype(str).tolist()
['Sales', nan, nan]          # the two missing values are still float NaN, NOT the string "nan"
>>> [type(v) for v in pd.Series(['Sales', None, np.nan]).astype(str)]
[<class 'str'>, <class 'float'>, <class 'float'>]
```

A raw `float('nan')` therefore survived into `variants_by_key`'s `Counter` keys (`department_normalizer.py:184`, pre-fix) and, whenever a missing-department row was the *most common* raw variant for its group, into `display_labels` (`:191`, pre-fix) as the value shown to the user. `_find_unmerged_similar_variants()` (`:186`) then iterated over every display label's characters via `_is_latin_script()` (`:108-109`) — `for c in s` — which raised `TypeError: 'float' object is not iterable` the moment `s` was that stray `nan` float, not a string.

This was a genuine gap in the department-normalization fix itself (Bug 1, §1) — every one of the three consuming modules (`employee_risk_scoring.py`, `overtime_cost_intelligence_engine.py`, `payroll_movement_tracker.py`) calls into `normalize_department_series()`, so any dataset with a `None`/`NaN`/empty-string department value crashed all three. `employee_risk_scoring.py` was independently safe (its `_safe_str()` helper, `:867-871`, already converted NaN to `None` *before* the `or "Unknown"` fallback — and `None` is falsy, so that fallback correctly fires), but `overtime_cost_intelligence_engine.py:308` and `payroll_movement_tracker.py:256,382` pass `df[dept_col].astype(str)` straight into the normalizer, so they hit the bug directly.

### Test-first reproduction

Added to `tests/test_department_normalization_phase35_5.py`, confirmed failing with the exact reported error **before** any fix was applied:

```
tests/test_department_normalization_phase35_5.py::test_nan_department_value_does_not_crash FAILED
tests/test_department_normalization_phase35_5.py::test_none_department_value_does_not_crash FAILED
tests/test_department_normalization_phase35_5.py::test_missing_department_values_route_to_unknown_bucket FAILED
tests/test_department_normalization_phase35_5.py::test_mixed_valid_and_missing_departments_end_to_end_no_crash FAILED
  ...
  File "backend\core\department_normalizer.py", line 109, in _is_latin_script
    return all((not c.isalpha()) or ("a" <= c.lower() <= "z") for c in s)
E   TypeError: 'float' object is not iterable
4 failed, 1 passed, 13 deselected
```

### Fix

**`backend/core/department_normalizer.py`** — no generic try/except added; the actual type-safety gap was closed at its source:

- New `_is_missing_department(raw)` helper (`:106-122`) — checks `raw is None`, then `pd.isna(raw)` (catches float NaN, NaT, pandas `NA`), then falls back to `not str(raw).strip()` for empty/whitespace-only strings. Explicitly documents *why*: `astype(str)`/`str()` cannot be trusted alone to catch missing values on this pandas version.
- New `MISSING_DEPARTMENT_LABEL = "Unknown / Unspecified Department"` constant (`:89-92`) — the explicit bucket every missing-value row now routes into, rather than crashing or being silently dropped.
- `normalize_department_series()` (`:164`) now builds `raw_str` via `raw.map(lambda v: MISSING_DEPARTMENT_LABEL if _is_missing_department(v) else str(v))` (`:180`) instead of `raw.astype(str)` — the missing-value check runs **before** any string operation is attempted, guaranteeing every value that reaches `_exact_normalize()`, `variants_by_key`, and `display_labels` is a real Python `str`, never a float.
- `normalize_department_value()` (single-value wrapper, `:262`) updated to use the same `_is_missing_department()` guard instead of its previous `if raw is None` check alone, which had the identical NaN gap.

### Test results (after fix)

```
tests/test_department_normalization_phase35_5.py — 18 passed (was 4 failed, 14 passed)
```

All 4 previously-failing tests now pass, plus 2 more added: `test_astype_str_does_not_stringify_nan_on_this_pandas_version` (documents the root cause directly) and `test_mixed_valid_and_missing_departments_end_to_end_no_crash` (the exact live-testing fixture shape — a fully-empty row, an empty-string department, a `None` department, mixed with messy Sales/مبيعات/Finance/finance values — run through all three consuming modules).

### Full regression suite (after this fix)

| Checkpoint | Result |
|---|---|
| Before this correction round (end of prior session) | 39 failed, 1217 passed, 1 skipped |
| After §1-§3 (department normalization, dedup, sector benchmarking) | 39 failed, 1243 passed, 1 skipped *(+26)* |
| After this regression fix (§5) | 39 failed, **1249 passed**, 1 skipped *(+6: 4 new NaN-handling tests + 2 already-counted-as-failing-then-passing)* |

Same 39 pre-existing, unrelated `bcrypt`/passlib failures throughout. **Zero regressions from this fix.**

### Live re-verification

Rebuilt the messy test CSV to include the exact rows described: an empty-string `Department` (an `EMP006`-equivalent row), a `Department = None` row, and one fully-empty row (all columns `NaN`), on top of the existing Sales/مبيعات/Finance/finance/Operations mix and the EMP001 duplicate. Uploaded to both pages via a live Playwright session against the actual running backend + Vite dev server.

**Before this fix:** both pages returned `"Overtime cost analysis encountered an error: 'float' object is not iterable"` / `"Payroll movement analysis encountered an error: 'float' object is not iterable"` — confirmed by direct API call reproducing the exact reported error.

**After this fix, live in the browser, both pages fully render:**
- Overtime Cost Intelligence: 4-row department table — `Operations 44% (8/18)`, `Finance 45% (9/20)`, `Sales 25% (5/20)`, `Unknown / Unspecified Department 33% (1/3)` — plus the "Department names normalized" box showing the Sales/مبيعات and Finance/finance merges.
- Payroll Movements: same 4-row breakdown (`Unknown / Unspecified Department: 2`, `Finance: 20`, `Sales: 20`, `Operations: 18`), same merge disclosure visible.
- Zero console errors on either page.
- The duplicate-row disclosure (Bug 2) still renders correctly above both tables, confirming this fix did not disturb it: *"1 duplicate row(s) removed before analysis (matched by 'EmployeeID')... 62 row(s) in the original upload, 61 remain."*

Screenshots: `03_overtime_nan_fix.png`, `04_payroll_nan_fix.png`.

---

## Summary Table

| Bug | Root cause file:line | Fix file:line | New tests | Live-verified |
|---|---|---|---|---|
| 1. Department normalization | `employee_risk_scoring.py:875` (root), `overtime_cost_intelligence_engine.py` groupby, `payroll_movement_tracker.py` ×2 groupby | `department_normalizer.py` (new) + 3 call sites updated | 12 | ✅ both pages, screenshots on file |
| 2. Duplicate rows | `secure_file_ingestion.py` — counted but never removed | `secure_file_ingestion.py:223,424` + `local_analysis_routes.py:1408,1524` | 10 | ✅ both pages, screenshots on file |
| 3. Sector benchmarking location | Unreachable from any live page (exporters only) | `overtime_cost_intelligence_engine.py:55-56,270-284` (wired into the one live page that already imports the salary engine) | 4 | ✅ badge visible, screenshot on file |
| 5. NaN/None/empty department crash (regression from #1) | `department_normalizer.py:171` (pre-fix) — `astype(str)` doesn't stringify NaN on pandas 3.0.3 | `department_normalizer.py:106-122,180,262` | 6 | ✅ both pages, screenshots on file |
| **Total** | | | **32 new tests, all passing** | Full regression: 1217 → 1249 passed, same 39 pre-existing unrelated failures |

**Screenshots:** `00_overtime_idle.png`, `01_overtime_corrected.png`, `02_payroll_corrected.png` (Bugs 1-3 verification), `03_overtime_nan_fix.png`, `04_payroll_nan_fix.png` (regression-fix verification) — all Playwright, full-page, captured against the live running backend (`python backend/api/main.py`, port 8000) and Vite dev server (port 5173).

**Operational note:** as flagged in the prior report, a stale backend process from an earlier session was still bound to port 8000 and could not be stopped via `taskkill`/`Stop-Process` by its PID as reported by `netstat` — it was a multiprocessing child of a different, unlisted parent PID. Resolved by identifying the actual process via `Get-CimInstance Win32_Process` (which lists real command lines) and stopping that PID directly. If a future session needs to restart the backend and it appears to already be running with stale behavior, check `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` for the real PID and command line rather than trusting `netstat`'s PID column alone.
