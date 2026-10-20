# Phase 8 — Succession Planning / Internal Mobility Readiness Engine

Status: **Implemented, tested, wired live, and verified in-browser.** Part 2
(Nitaqat cross-link) was assessed for risk and built — not deferred — after
the investigation below found a way to do it without any engine-to-engine
coupling or refactor risk to Phase 7 code.

---

## 1. Why this isn't the old `CareerProgression`/`TenureRatio`

Per `SUCCESSION_READINESS_INVESTIGATION.md`, those two constructs in
`backend/core/theory_grounded_construct_engine.py` are:
- **Dead** — reachable only from `/api/v1/analyse` and `/api/v1/upload`
  (`main.py`), endpoints `executive-ui` never calls.
- **Uncomputable against any real data available today** — `TenureRatio`
  requires `TotalWorkingYears`, a column absent from every fixture in this
  repo.

Per instruction, `YearsAtCompany` was **not** substituted for
`TotalWorkingYears` — that would silently change the ratio's Mobley-theory
meaning (organizational tenure vs. total career tenure) and produce a
near-constant, non-discriminating value for anyone with meaningful company
tenure. Instead, a new engine was built from columns confirmed present in
real data: `PerformanceRating`, `YearsAtCompany`, and optionally `JobLevel`
and `PromotionFairness`.

---

## 2. Formula (Part 1)

`backend/core/succession_readiness_engine.py:30-46` (module docstring) and
`:311-346` (`_compute_candidate`):

```
performance_percentile = 100 * (rating - min_observed) / (max_observed - min_observed)
tenure_factor           = min(1.0, YearsAtCompany / TENURE_WINDOW_YEARS)   # TENURE_WINDOW_YEARS = 2.0
readiness_score          = performance_percentile * tenure_factor
```

- `performance_percentile` is **min-max normalized within the uploaded
  dataset's own observed range** — not a fixed assumed scale (1-4, 1-5,
  etc.), since different real HR exports use different rating scales. A
  constant-rating series returns the neutral 50.0 for every row rather than
  dividing by zero (`succession_readiness_engine.py:187-194`, tested in
  `test_constant_performance_series_returns_neutral_percentile_not_divide_by_zero`).
- `tenure_factor` **saturates** at 1.0, it never explodes — a deliberate
  structural choice to avoid the near-zero-denominator blowup class this
  session already found and fixed in `ethical_ai.py`.
- Tiers: `High Readiness` ≥ 70, `Emerging Readiness` ≥ 40, else
  `Developing` (`succession_readiness_engine.py:134-138`).

**Honesty framing — explicitly a different caveat type than Nitaqat's.**
Nitaqat's caveat is "the official formula itself is unavailable." Here the
*inputs* are real; what's unvalidated is the *combination formula*. Every
result carries `is_validated_instrument=False`,
`calculation_confidence="constructed_heuristic_not_validated"`, and a
bilingual disclaimer (`succession_readiness_engine.py:140-156`). Confirmed
present in both:
- **API**: `succession_readiness_to_dict()` always includes
  `is_validated_instrument`, `calculation_confidence`, `disclaimer_en`,
  `disclaimer_ar` (`succession_readiness_engine.py:598-608`).
- **UI**: persistent amber banner rendered unconditionally
  (`SuccessionReadinessTracker.tsx:198-207`), plus the disclaimer + formula
  text rendered a second time alongside results
  (`SuccessionReadinessTracker.tsx:398-406`).

### Optional signals, graceful degradation
- **"Stuck high performer"** (needs `JobLevel`): flags top-quartile
  performance + top-quartile tenure *within the same JobLevel peer group*,
  skipping any peer group smaller than `MIN_PEER_GROUP_SIZE_FOR_STUCK_SIGNAL
  = 5` (`succession_readiness_engine.py:405-418`).
- **High readiness + low promotion-fairness** (needs `PromotionFairness`):
  flags readiness ≥ 70 AND fairness percentile ≤ 25
  (`succession_readiness_engine.py:420-432`).
- Absent columns never fabricate a signal — `columns_detected` reports what
  was found, and the UI shows "—, needs JobLevel" / "needs
  PromotionFairness" on the relevant KPI cards
  (`SuccessionReadinessTracker.tsx:311-320`).

### Designed for future enhancement, not rebuild
`_compute_candidate()` (`succession_readiness_engine.py:311-346`) already
carries `total_working_years`, `promotion_date_years_ago`, and
`training_completions` as documented, currently-unused optional parameters
— the extension point for a future session, per instruction.

---

## 3. Part 2 — Nitaqat cross-link: built, not deferred

**Risk assessment performed before writing any code.** The obvious design
(succession engine imports Nitaqat's per-employee classification) was
rejected: no engine in this codebase imports another engine's internals
(`department_normalizer.py` is a shared *utility*, not an engine — this
would have been a first, and thus a real architectural risk).

A second, real risk was found and designed around: a **positional-ID
mismatch**. If either engine fell back to a positional index when no named
`EmployeeID` column exists, the two engines' positions would not refer to
the same employee — each is computed over a *differently filtered* row
subset (valid-Nationality rows vs. valid-PerformanceRating+YearsAtCompany
rows). Joining on mismatched positional IDs would silently pair the wrong
employees — exactly the "looks scientific, carries no real signal" failure
class this session exists to prevent.

**Resolution:** `get_saudi_status_by_record_id()` in
`nitaqat_compliance_engine.py:466-522` (new, additive-only function, zero
changes to any existing Phase 7 function or dataclass) refuses (`returns
None`) whenever no named ID column (`EmployeeID`/`employee_id`/`EmpID`/
`emp_id`) exists in the upload, rather than risk a silent wrong join. The
actual join happens in the **route layer**
(`local_analysis_routes.py:1927-2071`, new `/succession-readiness`
endpoint), which already imports both engines independently — keeping the
two engine modules fully decoupled.

One small additive change was needed in the succession engine itself (my
own brand-new module, not existing Phase 7 work): `high_readiness_record_ids`
was added to `SuccessionReadinessResult` (`succession_readiness_engine.py:236-237`)
because `top_candidates` is capped at the top 20 for display — the
cross-link needs *every* high-readiness employee's ID, not just the
display slice (`test_high_readiness_record_ids_covers_full_count_not_just_top_20`).

Live confirmed: `succession_test_data.csv` (has both `Nationality` and
`EmployeeID`) → "Of 10 employees in the 'High Readiness' tier, 6 are
recorded as Saudi nationals." Independently recomputed outside the route
(§5) and matched exactly. `test_employee_data.csv` (no `Nationality`
column) → honest `"No cross-link possible — this upload needs both a
nationality/Saudi-status column and a named employee-ID column..."`

---

## 4. Test results (Part 3)

```
tests/test_succession_readiness_engine.py .......................... 27 passed
tests/test_nitaqat_compliance_engine.py ....................... 28 passed (22 pre-existing + 6 new)
```

Highlights (all real computed-value assertions, not smoke-only):
- `test_readiness_scores_match_independent_hand_computation` — formula
  reimplemented independently in the test file, not calling the engine's
  own helpers, exact match asserted.
- `test_real_employee_fixture_aggregate_matches_independent_recomputation`
  — `test_employee_data.csv` (200 rows), aggregate `n_high_readiness` and
  `avg_readiness_score` independently recomputed and matched exactly.
- `test_stuck_high_performer_signal_fires_for_exactly_four_of_five_engineered_rows`
  — a deliberately engineered **boundary case**: 5 employees built to be
  "stuck" (JobLevel=2, top performance, 7.3–8.4yr tenure vs. 7 peers at
  0.7–3.9yr). The lowest-tenure one (7.3yr) sits at exactly the 66.7th
  percentile of its 12-member peer group — below the 75th-percentile
  cutoff — so it must NOT fire while the other four (75th–100th
  percentile) must. Verified against specific hashed employee IDs.
- `test_high_readiness_low_fairness_combination_fires_for_all_five_engineered_rows`
  — 5 employees engineered with `PromotionFairness=1`, verified by hashed
  ID.
- `test_saudi_status_map_uses_same_hash_scheme_as_succession_engine` — the
  cross-link hash scheme independently reimplemented and matched.
- `test_duplicate_row_removed_by_pipeline_level_dedup` — confirms
  `SecureFileIngestion.scan()` reuse, no second dedup implementation.

New fixture: `succession_test_data.csv` (61 rows incl. 1 duplicate, 60
unique) — `EmployeeID`, `Department` (mixed Arabic/English/casing:
`Sales`/`مبيعات`, `Finance`/`finance`, `Operations`/`Operations `),
`JobLevel`, `PerformanceRating`, `YearsAtCompany`, `PromotionFairness`,
`Nationality` (mixed Saudi/non-Saudi tokens, EN/AR) — with the 5+5
engineered rows described above, plus missing values in rows 6-8.

---

## 5. Live browser verification

Backend: `python backend/api/main.py`. Frontend: `npm run dev` in
`executive-ui/`. Verified via Playwright against the running dev servers,
console errors captured: **`[]`** (empty) across all three scenarios.

1. **`succession_test_data.csv`** (has everything, incl. cross-link data) →
   `Employees Evaluated: 58` (60 unique − 2 missing perf/tenure),
   `High Readiness: 10` (avg score 41.8), `Stuck High Performers: 4`,
   `High Readiness + Low Fairness: 5`, top-candidates table, department
   breakdown, department-normalization notes, and the **Nitaqat cross-link
   banner**: *"Of 10 employees in the 'High Readiness' tier, 6 are recorded
   as Saudi nationals."* Independently recomputed outside the route:
   `n_total=58, n_high_readiness=10, n_saudi_high_readiness=6` — exact
   match. Screenshot: `succession_full_result.png`.
2. **`nitaqat_test_data.csv`** (no PerformanceRating/YearsAtCompany) →
   honest *"Performance/tenure data not detected in this upload"* with the
   full "columns that would activate this feature" checklist. Screenshot:
   `succession_not_detected.png`.
3. **`test_employee_data.csv`** (has PerformanceRating/YearsAtCompany, no
   JobLevel/PromotionFairness/Nationality) → `available=True` core path,
   KPI cards for the two optional signals honestly show `—` / "needs
   JobLevel" / "needs PromotionFairness", and the cross-link honestly shows
   *"No cross-link possible..."* since no Nationality column exists.
   Screenshot: `succession_core_only.png`.

Formula and disclaimer are rendered in full on every `available=True`
result, not just as a top banner — confirmed in all three screenshots.

---

## 6. Regression suite

```
Before + after (same run, no separate baseline needed — Phase 8 code is
purely additive: 1 new engine file, 1 new route, 1 new page, and additive-
only edits to nitaqat_compliance_engine.py / succession's own new dataclass):

py -m pytest tests/ -q
  1346 passed, 39 failed, 1 skipped   (1386 collected)

py -m pytest tests/ -q --ignore=tests/test_phase30_1_security.py
  1327 passed, 1 skipped, 0 failed
```

All 39 failures are confined to `tests/test_phase30_1_security.py` and
share one root cause, confirmed via direct traceback:

```
passlib.exc.MissingBackendError: bcrypt: no backends available --
recommend you install one (e.g. 'pip install bcrypt')
```

A pre-existing missing `bcrypt` pip package in this environment —
unrelated to any file touched this session (no succession/Nitaqat/HR-engine
code touches passlib, bcrypt, or auth). **Zero regressions** from Phase 8
work: 1327/1327 passing outside that one unrelated environment gap, of
which 33 are new tests added this phase (27 succession + 6 Nitaqat
cross-link) — all passing on first run with no fixes needed.

---

## 7. Files changed

| File | Change |
|---|---|
| `backend/core/succession_readiness_engine.py` | **New.** ~615 lines. |
| `backend/core/nitaqat_compliance_engine.py` | Additive: `get_saudi_status_by_record_id()` (+`import hashlib`). No existing function/dataclass altered. |
| `backend/api/local_analysis_routes.py` | New `/succession-readiness` route + 2 new imports. |
| `executive-ui/src/pages/SuccessionReadinessTracker.tsx` | **New** page. |
| `executive-ui/src/types/index.ts` | `NavPage` +`'succession'`. |
| `executive-ui/src/layout/Sidebar.tsx` | Nav entry, appended to the existing "Analysis" group after Nitaqat — matches the flat pattern every prior Phase 4-7 module used (Overtime, Payroll, Exit Interview, Recruitment, Fairness, Nitaqat were all appended to the same group rather than each getting its own section), so consistency with the established IA took priority over a new "Talent Development" grouping for a single item. |
| `executive-ui/src/App.tsx` | Route case for `'succession'`. |
| `tests/test_succession_readiness_engine.py` | **New.** 27 tests. |
| `tests/test_nitaqat_compliance_engine.py` | +6 tests for the cross-link function. |
| `succession_test_data.csv` | **New** fixture. |
