# Phase 20 — 5th Dimension: Academic Qualification (Job Pattern Grouping Engine)

Extends Phase 19's `job_pattern_grouping_engine.py` from 4 grouping dimensions (job
title × level × department × experience band) to 5 (+ academic qualification), live-
verified against the real dataset the brief named.

## A note on the dataset path first

The brief refers to `Original_Dataset_of_Employee_Attrition`. As already flagged in the
Phase 18 report, this file is **not checked into the `Adaptive_Workforce_AI` repo** —
only `saudi_attrition_normalizer.py` and `SAUDI_ATTRITION_DATASET_MAPPING_AUDIT.md`
(a prior audit built against it) live in-repo. The real file exists elsewhere on this
machine, confirmed by search:
`C:\Users\PvP-Pc\Desktop\datasetssaudi\Original Dataset of Employee Attrition (1).xlsx`
(1,191 rows × 35 columns — matches the audit doc's own row/column counts exactly). This
is the file used for every real-data figure in this report.

## 1. Detection pattern for the qualification column(s)

[`backend/core/job_pattern_grouping_engine.py:225-239`](backend/core/job_pattern_grouping_engine.py#L225-L239):

```python
_ACADEMIC_DEGREE_PATTERNS = re.compile(
    r"\b(academic[_\s]?degree|education[_\s]?level|qualification|degree[_\s]?level|"
    r"highest[_\s]?degree|degree|"
    r"المؤهل[_\s]?العلمي|الدرجة[_\s]?العلمية|المستوى[_\s]?التعليمي)\b",
    re.I,
)
_EDUCATION_FIELD_PATTERNS = re.compile(
    r"\b(education[_\s]?field|field[_\s]?of[_\s]?study|major|specialization|"
    r"academic[_\s]?major|study[_\s]?field|"
    r"التخصص[_\s]?الأكاديمي|مجال[_\s]?الدراسة|التخصص)\b",
    re.I,
)
```

**Two genuinely separate signals, detected independently** — the exact "never conflate"
principle `contract_expiry_engine.py` established for ContractEndDate vs. IqamaExpiry.
Confirmed against the real dataset: its raw column is literally `'\xa0Academic_degree '`
(NBSP prefix + trailing space — the same real-world messiness
`saudi_attrition_normalizer.py` already documents), and `_find_column()`'s
`pattern.search()` correctly matches it despite the surrounding whitespace/NBSP, since
regex search doesn't require an exact full-string match. The real dataset has **no**
separate field/major column at all (confirmed against its full 35-column schema in
`SAUDI_ATTRITION_DATASET_MAPPING_AUDIT.md`), so `_EDUCATION_FIELD_PATTERNS`' composite-
label code path is exercised only by the new synthetic fixture
(`job_pattern_qualification_test_data.csv`) — stated honestly in the module docstring
rather than implied to work on data that never actually exercised it.

**Degree-level normalization reuses the same two-tier architecture** as Phase 19's job-
title normalization (`normalize_degree_series()`,
[line 461](backend/core/job_pattern_grouping_engine.py#L461)): exact-normalize (trim +
casefold) always, plus a small curated EN/AR synonym table
([lines 195-206](backend/core/job_pattern_grouping_engine.py#L195-L206)) — grounded in
the **real** values observed in the attrition dataset (`Bachelor's` / ` Bachelor's` /
`Diploma or secondary` / ` Master's` / `Ph.D`) rather than invented. Kept as separate,
independently-tested code from `normalize_title_series()` rather than a shared
parametrized helper — a deliberate risk-reduction choice, documented in the module
docstring: 15 pre-existing Phase 19 tests already depend on `normalize_title_series()`'s
exact behavior, and refactoring it mid-phase to share internals with a brand-new degree
normalizer carried more regression risk than ~40 lines of duplication.

**Qualification gets its own dedicated column**, not a suffix on Job Title — Level,
Department, and Experience Range already each render as their own column in both the
on-screen table and the Excel export; folding qualification into the Job Title string
would break that established one-dimension-per-column convention. Pattern IDs stay plain
sequence numbers ("P001", "P002"...), unchanged — none of the other 4 dimensions are
encoded into the ID either. Reasoning documented in full in the module docstring
([lines 60-68](backend/core/job_pattern_grouping_engine.py#L60-L68)).

## 2. Before/after pattern count on real data

Measured directly against the real 1,191-row dataset:

| | Dimensions | Pattern count |
|---|---|---|
| **Before** (Phase 19, unmodified 4-dim grouping, same file) | title × department × experience (no JobLevel column in this dataset) | **118** |
| **After** (Phase 20, 5-dim grouping, same file) | + academic qualification | **218** |

218 patterns from 1,191 employees is still a genuine **~5.5x reduction** — well under
the "1000 individual employees" baseline that motivates this feature, even though it's
a real, visible increase over Phase 19's 118 (the 5th dimension is doing real work, not
sitting inert). Live-verified on screen and in the downloaded Excel file (§5): both show
exactly 218 (200 displayed on screen/in the capped export view, 18 additional disclosed
via the existing truncation banner — the same `_MAX_DISPLAY_PATTERNS=200` cap Phase 19
already had, unchanged).

**Important honest caveat found while measuring this**: on this specific real dataset,
the "experience" dimension (`Years_Experience`) contributes **nothing** to either the
before or after count — its values are range-text ("Less than 5 years", "From 5 to 10
years"), which Phase 19's numeric-only `pd.to_numeric(errors="coerce")` parser cannot
read, so `experience_bucket` is `None` for all 1,191 rows in both counts. The 218-vs-118
increase is therefore driven entirely by department already contributing (it did in
Phase 19 too) plus academic qualification newly contributing — not by an interaction
between qualification and a working experience dimension. This is disclosed explicitly
in the module docstring's "known limitation" section (§3 below) rather than silently
assumed to be part of the improvement.

## 3. Minimum-group-size floor — how the tradeoff was resolved

`MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE` was **left unchanged at 3**, backed by a real
measurement rather than left on assumption:

- Of the 200 displayed 5-dimension patterns, 112 fall under the floor (n<3) — a real,
  visible increase in small-pattern *count* versus Phase 19.
- But by **employee coverage**, the picture is healthy: 1,032 of 1,191 employees (~87%)
  still land in a pattern *at or above* the floor. The long tail of small patterns is
  genuinely rare title+department+experience+qualification combinations (e.g. a single
  "Lawyer / Legal Affairs / Master's" employee) — a true small sample, not an artifact of
  a miscalibrated floor. Suppressing those specific figures is correct, not a
  degradation.
- Lowering the floor below 3 was rejected regardless of these numbers: 2 employees'
  "aggregate" is still just two people's literal salary.

Full reasoning documented at
[`backend/core/job_pattern_grouping_engine.py:239-256`](backend/core/job_pattern_grouping_engine.py#L239-L256).

**A second, real finding surfaced by this same measurement, fixed as part of this
phase** (not scope creep — it directly blocks a trustworthy answer to "does the floor
still hold"): a genuinely missing job title was being silently fabricated into its own
`"Unknown / Unspecified Job Title"` pattern instead of being excluded, because the
missing-value sentinel passes through the same exact-normalize (trim+casefold) tier as
every real value before becoming a grouping key — so the original code's
`title_key == MISSING_TITLE_LABEL` comparison (against the un-normalized, original-case
constant) silently never matched and never excluded anything. This bug pre-dates this
phase (it was already present in Phase 19's code, just never triggered — no Phase 19
fixture had an actually-missing title value) and was caught here because the identical
pattern was being written fresh for the new degree-missing-value check. Fixed in both
places at once via `_MISSING_TITLE_KEY`/`_MISSING_DEGREE_KEY` (pre-computed casefolded
sentinels compared against instead — see
[lines 384-393](backend/core/job_pattern_grouping_engine.py#L384-L393)), with a
regression test (`test_missing_job_title_row_excluded_not_fabricated_as_pattern`)
reproducing the exact failure mode with a minimal 2-row fixture. **This bug did not
affect this report's real-dataset pattern counts** — the attrition dataset has no
missing `JobTitle` values, confirmed by re-running the before/after measurement after
the fix and getting the identical 118/218 figures.

**Separately documented, deliberately out of scope**: live-testing against the real
dataset also surfaced that its `MonthlySalary` column is range-text ("From 5000 to 10000
S.R", "Less than 5000 SAR") — Phase 19's numeric-only salary parser reads zero valid
values from it company-wide, so every pattern's salary is unavailable on this dataset,
independent of the floor. This is a pre-existing Phase 19 limitation, not something this
phase's 5th-dimension task was scoped to fix (the reusable fix already exists as
`saudi_attrition_normalizer._parse_salary_range()` — a natural follow-up, not attempted
here). To keep the floor's *salary* behavior actually testable under the 5-dimension
split, a new synthetic fixture with working numeric salary
(`job_pattern_qualification_test_data.csv`) was built specifically to verify it — see
`test_qualification_dimension_produces_finer_grained_split`, which confirms a 3-employee
sub-pattern correctly shows a real salary figure while a 2-employee sub-pattern of the
same base group correctly suppresses. The engine's narrative text was also extended
(a small, directly-related fix) to distinguish "salary column detected but 0 values
parsed dataset-wide" from "this pattern has too few employees" — because without it, the
per-row `"Suppressed (n<3)"` badge on the real dataset (where literally every pattern
shows this, since salary is 0% parseable) would read as a small-sample-size finding when
the real cause is a parsing gap. The **narrative banner** correctly disambiguates this
live (see screenshot 1, §5); the per-row badge label itself was deliberately left
unchanged, so on this real dataset it still reads `"Suppressed (n<3)"` even on rows with
employee_count 3 or 4 — an honest observation from live-testing, not something to
paper over: `n_with_valid_salary` (which the badge is really keyed on) is what matters,
and it actually is 0 for every pattern, so "n<3" is not literally false — but a reader
looking only at the table without the narrative above it could reasonably read it as a
sample-size problem. Flagged here explicitly as a known, minor, unresolved rough edge
rather than left for a future session to discover independently.

## 4. Test results

`tests/test_job_pattern_grouping_engine.py` — **24/24 passed** (15 Phase 19 + 9 new
Phase 20 tests; the one Phase 19 test whose expected Excel column list needed updating
for the new "Academic Qualification" column was also updated, not counted as new):

```
$ python -m pytest tests/test_job_pattern_grouping_engine.py -v
...
24 passed in 0.89s
```

New Phase 20 coverage:
- **Degree-level normalization**: real whitespace variant (`"Bachelor's"` /
  `" Bachelor's"`) and 3-way EN/EN-abbrev/AR variant (`"Ph.D"` / `"PhD"` / `"دكتوراه"`)
  each merge to one canonical key — grounded in the real attrition dataset's own values.
- **Composite label**: degree + field present together → `"Bachelor's — Marketing"`,
  not just the degree alone.
- **Finer-grained split** (the brief's own example): 5 "Sales Executive / Sales / 3
  years" employees split into a 3-person "Bachelor's — Marketing" pattern (salary
  computed normally) and a 2-person "Bachelor's — Engineering" pattern (correctly
  suppressed) — proving the 5th dimension changes real grouping outcomes.
- **Missing qualification value**: excluded from the qualification key (`None`), not
  guessed — distinct pattern, not dropped.
- **No-qualification-column fallback**: `test_employee_data.csv` (no `Academic_degree`
  column) still groups on the original 4 dimensions, `"academic_qualification"` correctly
  absent from `grouping_dimensions_used`, disclosed in the narrative.
- **Direct 4-vs-5-dimension comparison on identical rows**: the qualification fixture
  analyzed with vs. without its two qualification columns dropped produces strictly more
  patterns with them present — direct proof, not inference.
- **Regression test** for the missing-title bug described in §3.
- **Excel export**: the new "Academic Qualification" column is present with real values;
  the PII-safety guarantee (no employee IDs anywhere in either sheet) was re-verified
  against the new 9-column export, not just assumed to still hold.

## Full regression suite

```
$ python -m pytest tests/ -q
40 failed, 1419 passed, 1 skipped, 205 warnings in ~52s
```

1419 passed = the 1410 baseline after Phase 19 + 9 net new Phase 20 tests. Same 40
pre-existing, unrelated failures (`test_phase29_extended.py`, `test_phase30_1_security.py`)
— **zero regressions**.

## 5. Live browser verification

Backend restarted (no auto-reload) to pick up the unchanged routes with the updated
engine; frontend restarted after adding the Qualification column. `npx tsc --noEmit`
passed with zero errors. Same stale, unowned `127.0.0.1:8000` socket noted in the Phase
18/19 reports was still present — worked around identically (temporary Vite proxy
redirect to the backend's real `192.168.100.2:8000` LAN binding for this verification
session only, reverted immediately after).

**Screenshot 1 — real dataset, top of page**: uploaded the real `Original Dataset of
Employee Attrition (1).xlsx` directly (1,191 rows). KPIs show **1,191 → 218 patterns**
exactly matching the offline-computed figures in §2. The narrative text correctly states
the salary-parsing limitation from §3 (*"salary figures are not available for this
upload, not suppressed for having too few employees"*) and lists
`job_title, department, experience, academic_qualification` as the dimensions used
(job_level absent, correctly disclosed).

**Screenshot 2 — pattern table with the new Qualification column, scrolled**: real,
distinguishable rows — e.g. "Marketing Specialist" appears twice as two genuinely
different patterns (Marketing dept / Diploma-or-Secondary vs. Administration dept /
Bachelor's), and "Administrative manager / Administration / PhD" appears as its own
pattern separate from the Bachelor's- and Master's-qualified Administrative managers —
concrete, real evidence the 5th dimension is subdividing patterns exactly as intended.

**Downloaded Excel file, inspected directly**: `Job_Pattern_Market_Research_Worksheet.xlsx`
downloaded via the same button, saved and read back with `pandas.read_excel`. Confirmed:
- **Instructions** sheet: 7 rows (up from Phase 19's 6) — the new "Academic
  Qualification" explanation row present with the exact wording from the module.
- **Job Patterns** sheet: 200 rows × **9 columns** (Pattern ID, Job Title, Level,
  Department, **Academic Qualification**, Experience Range, Employee Count, Current Avg
  Salary, Current Salary Range) — the new column populated with real values (`Bachelor's`,
  `Master's`, `PhD`, `Diploma or Secondary`) matching the on-screen table exactly, `Level`
  correctly blank throughout (no JobLevel column in this dataset — no fabricated value).

Zero console errors or page errors across the full flow, including the qualification-
enabled file-download step.

## Files changed

- `backend/core/job_pattern_grouping_engine.py` (5th dimension, degree normalizer,
  composite-label logic, floor re-verification, missing-title bug fix, Excel column,
  Instructions-sheet update — module docstring extended with full rationale for every
  judgment call)
- `tests/test_job_pattern_grouping_engine.py` (+9 tests, 1 existing test updated for the
  new Excel column)
- `job_pattern_qualification_test_data.csv` (new fixture, repo root)
- `executive-ui/src/pages/JobPatternGroupingTracker.tsx` (Qualification column in the
  on-screen table, EN/AR column labels for the two new optional source columns, degree
  normalization-notes banner)
