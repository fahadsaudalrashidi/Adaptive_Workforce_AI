# Phase 5 Report — Recruitment Pipeline Status Tracker

Date: 2026-08-06
Scope: a fifth live module, the first on this platform to cover hiring (who is being brought in) rather than retention/attrition (who might leave). Follows on from `PHASE_4_CORRECTIONS_REPORT.md`.

**Verification method for every claim below:** direct code inspection (file:line citations), a dedicated pytest file with real computed-value assertions (funnel counts, conversion rates, and time-to-hire independently hand-computed and compared exactly against the engine's output — not smoke tests), a full regression run of the pre-existing suite before and after, and a live Playwright browser session against the actual running backend + Vite dev server covering all three required scenarios (messy funnel data, dedup/date-quality warnings, and the honest "not detected" state against the platform's real existing dataset), screenshots taken, console errors checked.

---

## 1. Files created / modified

| File | Status | Purpose |
|---|---|---|
| `backend/core/recruitment_pipeline_engine.py` | new (680 lines) | Core engine — `analyze_recruitment_pipeline(df)` |
| `tests/test_recruitment_pipeline_engine.py` | new (337 lines, 22 tests) | Real computed-value tests, all 3 required scenarios |
| `executive-ui/src/pages/RecruitmentPipelineTracker.tsx` | new (552 lines) | Live frontend page |
| `backend/api/local_analysis_routes.py` | modified | +import block (`:116-117`), +endpoint `POST /api/local/recruitment-pipeline` (`:1535-1638`) |
| `backend/core/secure_file_ingestion.py` | modified | `_ID_COLUMN_PATTERNS` (`:107`) extended to recognise `candidate_id`/`applicant_id` for precise ID-based dedup on recruitment data, not just HR `employee_id` |
| `executive-ui/src/layout/Sidebar.tsx` | modified | +`UserPlus` icon import, +nav item `id: 'recruitment'` in the Analysis group |
| `executive-ui/src/App.tsx` | modified | +import, +`case 'recruitment'` |
| `executive-ui/src/types/index.ts` | modified | +`'recruitment'` to `NavPage` union |

**Live route confirmed mounted:**
```
POST /api/local/recruitment-pipeline
```
(verified directly: `create_local_analysis_router()`'s route list was inspected and contains this exact path — same verification method as every prior phase report.)

**Live frontend page confirmed:** "Recruitment Pipeline" in the sidebar's Analysis nav group (same group as Overtime Cost Intelligence, Payroll Movements, Exit Interview Intelligence), reachable via `App.tsx`'s `case 'recruitment'`.

---

## 2. What was reused vs. newly built (per explicit instruction)

| Requirement | What was reused | Where |
|---|---|---|
| Column detection | This codebase's established local-regex `_find_column()` convention (already used by every Phase 4/35 module) — `theory_aware_column_mapper.py` and `saudi_schema_intelligence.py` were both reviewed first and rejected as fits: the former is built around Likert-scale psychological survey columns (`ConstructDefinition`), the latter is a whole ERP-schema classifier — neither matches a small fixed set of recruitment funnel fields | `recruitment_pipeline_engine.py:97-135` (10 `re.compile` patterns, English + Arabic combined per field, same style as `payroll_movement_tracker.py`'s `_EMPLOYEE_ID_PATTERNS` etc.) |
| Department/role grouping | `backend/core/department_normalizer.py` — imported and called verbatim, not reimplemented | `recruitment_pipeline_engine.py:81`, called at `:378` |
| Deduplication | `SecureFileIngestion.scan()`'s existing pipeline-level dedup (Bug 2, `PHASE_4_CORRECTIONS_REPORT.md` §2) — runs automatically before this module ever sees the dataframe; no second dedup implementation was written | Confirmed via `test_duplicate_candidate_row_is_removed_by_pipeline_level_dedup` |
| Rejection-reason themes | `exit_interview_intelligence_engine.py`'s `analyze_exit_interview_text()` — called directly, same TF-IDF/keyword-construct approach, same privacy guarantees (no raw text returned, `MIN_RESPONSES_FOR_AGGREGATE=5` threshold) | `recruitment_pipeline_engine.py:82-86` (imports), called at `:512` |
| Cost per hire | `financial_intelligence_engine.py`'s existing `estimate_monthly_salary()` and `SECTOR_BENCHMARK_CONFIDENCE` constant — no sixth cost formula added | `recruitment_pipeline_engine.py:87-90` (imports), used at `:521-524` |

**Newly built, and why it could NOT be a reuse:** pipeline-stage normalization (`Applied`/`Screening`/`Interview`/`Offer`/`Hired`/`Rejected`, each with English/Arabic/casing variants — e.g. `"Interview"` vs `"مقابلة"`) is a *different value domain* from department names. `department_normalizer.py`'s synonym table is department-specific (`"Sales"` ↔ `"مبيعات"`) and has no stage vocabulary — routing stage values through it would silently fail to merge anything. Instead, the exact same *two-tier pattern* (trim+casefold, then a curated EN/AR synonym table, disclosed when it fires) was implemented locally as `_STAGE_SYNONYMS`/`_normalize_stage_series()` (`recruitment_pipeline_engine.py:150-215`) — mirroring how `overtime_cost_intelligence_engine.py` and `payroll_movement_tracker.py` each already keep their own local salary/hours patterns rather than sharing an unrelated module's domain table. This is documented explicitly in the module's own docstring (`:59-70`) so the design choice is traceable, not silent.

---

## 3. Cost-per-hire — explicitly no sixth formula, no fabricated Saudi-specific number

Per instruction, this module never introduces a new cost formula:

- **When the dataset has a real recruitment-cost column** (`RecruitmentCost`/`CostPerHire`/`AgencyFee`/etc., detected via `_RECRUITMENT_COST_PATTERNS`, `recruitment_pipeline_engine.py:96-99`), the average of that column is used directly — `cost_per_hire_confidence = "observed"`.
- **When it doesn't**, the module calls `financial_intelligence_engine.py`'s already-canonical `estimate_monthly_salary("diversified", "mid")` (the exact function `overtime_cost_intelligence_engine.py` already calls) and applies a single, explicitly-labeled, non-Saudi-specific multiplier (~20% of one year's estimated salary — a widely repeated general HR rule of thumb, not a citation), then reuses `SECTOR_BENCHMARK_CONFIDENCE` (`"uncalibrated_generic_estimate"`) imported directly from `financial_intelligence_engine.py` rather than redefining an equivalent string — the identical honesty pattern Phase 4 already established for its own uncalibrated salary fallback.
- **No number is produced at all when nobody in the dataset reached "Hired"** — `cost_per_hire_sar` and `cost_per_hire_confidence` are both `None` (verified: `test_cost_per_hire_none_when_no_one_hired`).

A live search for a freely citable Saudi-market cost-per-hire benchmark (mirroring Phase 4's GASTAT research effort) did not surface one — the same honest "no such source was found" outcome Phase 4 reported for its industry-vertical salary table, applied here to the same problem for hiring cost specifically.

---

## 4. The honest "not detected" path (required verification)

**What happens today when this feature is used against the platform's existing real test dataset** (`test_employee_data.csv` — the 200-row, genuine structured HR *employee* export used throughout Phases 1-4, with columns `EmployeeID, Department, Age, Gender, JobRole, Attrition, MonthlyIncome, OverTime, JobSatisfaction, PerformanceRating, YearsAtCompany`):

- `analyze_recruitment_pipeline()` detects **zero** of the 10 recruitment-related columns (`recruitment_pipeline_engine.py:333-368` — the gate is `stage_col is None`, checked first since a pipeline-stage column is the one essential signal a funnel cannot exist without).
- Returns `available=False` with `reason` explicitly stating *"This looks like structured HR employee data, not recruitment/candidate data"* and listing all 10 columns that would activate the feature (`_ALL_COLUMN_LABELS`, `recruitment_pipeline_engine.py:277-288`).
- **No funnel, no conversion rate, no time-to-hire figure is computed or returned** — `n_candidates_total=0`, `current_stage_distribution=[]`, `avg_time_to_hire_days=None`.
- Confirmed live in the browser (§6 below, screenshot `06_recruitment_not_applicable.png`): the page renders a clear "Recruitment pipeline data not detected in this upload" panel with a checklist of the 10 activating columns, all shown as absent except `Department/role applied for` (which the platform's HR data does have, but it alone is not sufficient — a stage column is still required).
- **This is not a crash and not fabricated data** — it is the same honest, disclosed "not applicable" pattern already established by Payroll Movements Tracker for snapshot-only data.

---

## 5. Funnel math — hand-verified

Test fixture (`tests/test_recruitment_pipeline_engine.py`'s `recruitment_df`): 20 synthetic candidates, stage assignment designed so the exact expected counts are known in advance: Applied(20) → Screening(15) → Interview(10) → Offer(6) → Hired(4), 4 Rejected.

| Assertion | Hand-computed expectation | Engine output | Test |
|---|---|---|---|
| Stage-reach counts | `{Applied:20, Screening:15, Interview:10, Offer:6, Hired:4}` | matches exactly | `test_funnel_counts_match_hand_computation` |
| Conversion rates | `15/20, 10/15, 6/10, 4/6` = `75.0%, 66.7%, 60.0%, 66.7%` | matches (rounded to 1dp) | `test_conversion_rates_match_hand_computation` |
| Biggest drop-off | lowest conversion = Offer (60.0%) | `"Offer"` | `test_biggest_dropoff_stage_is_the_lowest_conversion` |
| Time-to-hire | 4 hires, each exactly 20 days (`HireDate = ApplicationDate + 20d`) | `avg_time_to_hire_days == 20.0`, `n_time_to_hire_computed == 4` | `test_time_to_hire_matches_hand_computation` |
| Department hire rate | Sales: 10 candidates, 4 hired = 40.0%; Engineering: 10, 0 hired = 0.0% | matches exactly | `test_department_breakdown_hire_rate` |
| Source hire rate | Referral (first 5 rows, contains all 4 hires): 5 candidates, 4 hired = 80.0% | matches exactly | `test_source_breakdown_hire_rate` |

**Funnel convention, stated honestly (not hidden in fine print):** a typical recruitment CSV export is a snapshot of each candidate's *current or final* stage, not a per-candidate event-history log. The funnel therefore treats "reached Hired" as implying every earlier stage was also reached — a standard, disclosed convention (`governance_note`, `recruitment_pipeline_engine.py:571-577`), not a claim of observed per-candidate timestamps. Every candidate, including those later rejected, counts toward the "Applied" floor (rank 0) since being a row in a candidate dataset means they applied — they just don't count toward later stages, since there's no evidence of how far they progressed before rejection. This was caught and fixed during development: an earlier version excluded Rejected candidates from "Applied" entirely, undercounting it; fixed at `recruitment_pipeline_engine.py:435-440`.

---

## 6. Live verification — all three required scenarios

Built `messy_recruitment_data.csv` (56 rows) reusing the same messiness patterns as `messy_test_data.csv`: mixed Arabic/English/casing pipeline-stage names (`Applied`/`applied`/`تقديم`, `Interview`/`interview`/`مقابلة`, `Hired`/`hired`/`تعيين`, etc.), mixed department names (`Sales`/`مبيعات`, `Finance`/`finance`), one exact duplicate candidate row (`CAND001`), one impossible date sequence (a `HireDate` before its `ApplicationDate`), and one row with a missing `Stage` value. Uploaded to the live running backend (`python backend/api/main.py`, port 8000) + Vite dev server (port 5173) via Playwright.

### (a) Funnel view with correctly merged stage names — `05_recruitment_funnel.png`

- `messy_recruitment_data.csv · 55 rows` (56 → 55: the duplicate was removed — see (b))
- Funnel table: `Applied 55 (100.0%) → Screening 38 (69.1%) → Interview 28 (50.9%) → Offer 16 (57.1%→29.1%) → Hired 8 (50.0%→14.5%)`, `Rejected 7 (12.7%)`
- "Pipeline stage names normalized" disclosure box lists all 6 merges, e.g. *"Merged 'Interview', 'interview', 'مقابلة' into 'Interview'... {'interview': 3, 'Interview': 3, 'مقابلة': 6}"*
- "Department names normalized" box: *"Merged 'Finance', 'finance'..."*, *"Merged 'Sales', 'مبيعات'..."*
- Cost Per Hire: `SAR 13K` — `Observed (from your data)` (the fixture includes a real `RecruitmentCost` column)
- Zero console errors

### (b) Deduplication / date-quality warnings rendering — same screenshot, `05_recruitment_funnel.png`

- Amber disclosure directly under the filename: *"1 duplicate row(s) removed before analysis (matched by 'CandidateID' — the same ID appeared more than once). 56 row(s) in the original upload, 55 remain."*
- Second amber disclosure: *"1 row(s) had a hire date before the application date (an impossible sequence) — excluded from the time-to-hire average rather than silently producing a negative duration."*
- Both render above the KPI cards, matching the disclosure-first pattern already established for Overtime/Payroll.

### (c) "Not applicable" message against the real existing dataset — `06_recruitment_not_applicable.png`

- Uploaded `test_employee_data.csv` (the platform's real 200-row HR employee fixture, genuinely has no recruitment columns).
- Page renders: *"Recruitment pipeline data not detected in this upload"* + the full reason text + a checklist of all 10 activating columns (all unchecked except "Department/role applied for", which the HR data does coincidentally have).
- Zero console errors, zero fabricated numbers.

---

## 7. Full-Suite Regression Trail

| Checkpoint | Result |
|---|---|
| Before this phase (end of Phase 4 corrections) | 39 failed, 1249 passed, 1 skipped |
| After this phase | 39 failed, **1271 passed**, 1 skipped *(+22 new recruitment-pipeline tests)* |

Same 39 pre-existing, unrelated `passlib`/bcrypt environment failures throughout (reproduced directly: `passlib.exc.MissingBackendError: bcrypt: no backends available`, originating inside `passlib`'s own backend-selection code). **Net: zero regressions, +22 new tests, all passing.**

The `secure_file_ingestion.py` `_ID_COLUMN_PATTERNS` extension (candidate_id/applicant_id) was re-verified against the full existing dedup and Phase 9 ingestion test suites (`test_duplicate_row_deduplication_phase35_5.py`, `test_phase9_enterprise_upload_reporting.py`) — 55/55 passed, confirming the HR-employee dedup behavior is unchanged and the new pattern only adds recognition, never removes it.

---

## Summary Table

| Requirement | Status |
|---|---|
| New engine with graceful "not applicable" path | ✅ `recruitment_pipeline_engine.py`, verified against the real existing dataset |
| Funnel/conversion/drop-off/time-to-hire when data present | ✅ hand-verified exact match, §5 |
| Department normalization reuse | ✅ `department_normalizer.py` called verbatim |
| Rejection-reason theme reuse | ✅ `exit_interview_intelligence_engine.py` called verbatim |
| No new financial formula | ✅ `financial_intelligence_engine.py`'s `estimate_monthly_salary()` + `SECTOR_BENCHMARK_CONFIDENCE` reused |
| Live route + live page | ✅ `POST /api/local/recruitment-pipeline`, "Recruitment Pipeline" nav item |
| Bilingual EN/AR | ✅ every label, narrative, and disclosure has an Arabic string |
| Tests (with/without/messy data) | ✅ 22 tests, all passing |
| Live browser verification, 3 scenarios | ✅ `05_recruitment_funnel.png`, `06_recruitment_not_applicable.png`, zero console errors |
| Full regression | ✅ 1249 → 1271 passed, same 39 pre-existing unrelated failures |
