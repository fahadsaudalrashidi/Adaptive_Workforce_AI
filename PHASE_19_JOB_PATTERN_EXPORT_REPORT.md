# Phase 19 — Job Pattern Grouping & Market Research Export

New, fully offline module: groups the user's own uploaded workforce data into job
"patterns" (job title x level x department x experience band) and produces a
downloadable, aggregate-only Excel worksheet the user takes to an external tool of
their own choosing to research current market salary ranges. Zero network calls
anywhere in this module — see §3.

## 1. Normalization approach for job titles, and why

**Department normalization is real, unmodified reuse**: `analyze_job_pattern_grouping()`
imports and calls `department_normalizer.normalize_department_series()` directly
([`backend/core/job_pattern_grouping_engine.py:74`](backend/core/job_pattern_grouping_engine.py#L74)
and [line 419](backend/core/job_pattern_grouping_engine.py#L419)) — same function, same
import, zero duplicated logic.

**Job-title normalization could not be the same kind of reuse**, and this is disclosed
up front in the module docstring
([lines 10-23](backend/core/job_pattern_grouping_engine.py#L10-L23)):
`department_normalizer.py`'s curated synonym table works because there are only ~19
corporate department names in practice. Job titles have an effectively open,
compound-phrase vocabulary ("Senior Regional Sales Manager" vs. "Sr. Sales Mgr -
Regional") that a single shared lookup table sized for department names would not
generalize to.

Rather than cross-importing `department_normalizer.py`'s underscore-prefixed internals
(`_exact_normalize`, `_is_latin_script`, `_find_unmerged_similar_variants`) across a
module boundary they were never designed to expose, this module follows this session's
own established precedent for exactly this situation:
`recruitment_pipeline_engine.py`'s `_is_missing_value()`
([line 174](backend/core/recruitment_pipeline_engine.py#L174)) mirrors
`department_normalizer._is_missing_department()`'s discipline via a small local
reimplementation, with a docstring citing the original — not a private cross-import.
`job_pattern_grouping_engine.py`'s `normalize_title_series()`
([line 245](backend/core/job_pattern_grouping_engine.py#L245)) does the same: it
reproduces the **exact same two-tier architecture** as
`department_normalizer.normalize_department_series()` —

1. **Exact-normalize tier** (always applied): trim + casefold.
2. **Curated EN/AR synonym table** (small, disclosed, explicitly non-exhaustive — same
   shape as `EN_AR_DEPARTMENT_SYNONYMS`, ~22 entries covering common single/short-phrase
   Saudi/GCC titles: Manager, Engineer, Accountant, Sales Executive, HR Specialist, etc.,
   [lines 116-142](backend/core/job_pattern_grouping_engine.py#L116-L142)).
3. **Same-script near-duplicate flagging via `difflib`** at the same 0.82 similarity
   threshold department_normalizer.py uses — flagged for human review, **never**
   auto-merged, and cross-script (Arabic vs. Latin) pairs are never compared at all
   (not meaningful between scripts sharing no characters — identical principle to
   `department_normalizer.py`).

Verified live: a fixture with "Manager" / "manager" / "مدير" (three formats of the same
title) merged into one canonical "Manager" pattern with a correctly hand-computed
aggregate salary, while "Sales Executive" vs. "Sales Exective" (a one-character typo) was
flagged as a near-duplicate for human review but **stayed as two separate patterns** —
proving the "never guess" discipline holds even when it costs some grouping tightness.

## 2. Experience-bucket boundaries chosen and why

[`backend/core/job_pattern_grouping_engine.py:167-172`](backend/core/job_pattern_grouping_engine.py#L167-L172):

```python
_EXPERIENCE_BANDS = [
    (0, 2, "Entry-Level (0-2 yrs)"),
    (3, 5, "Mid-Level (3-5 yrs)"),
    (6, 10, "Senior (6-10 yrs)"),
    (11, None, "Expert / Leadership (11+ yrs)"),
]
```

Four bands mirroring common Gulf-region salary-survey conventions. Like every tier
boundary chosen this session (Phase 18's contract-expiry urgency tiers being the most
recent), this is explicitly disclosed as this platform's own illustrative heuristic, not
a certified industry standard — stated directly in `_SOURCES`
([line 259](backend/core/job_pattern_grouping_engine.py#L259)) and surfaced on-screen via
the sources footer.

**A pattern's displayed "Experience Range" is the *actual observed* min-max years within
that group, not the band's nominal range** — e.g. a "Mid-Level (3-5 yrs)" bucket whose
real members only span 3-4 years shows "3-4 years," not "3-5 years." This was a
deliberate choice to keep the exported figure honest and non-fabricated (the brief asks
for "the experience range covered," which is a claim about the data, not the bucket
label) — see `experience_range_label` computation at
[line 486](backend/core/job_pattern_grouping_engine.py#L486).

## 3. Zero network calls — confirmed

This module makes no HTTP/socket call of any kind: no `requests`, `httpx`, `urllib`, or
raw `socket` usage anywhere in `job_pattern_grouping_engine.py` (confirmed by inspection
— the only imports are `difflib`, `hashlib`, `io`, `re`, `collections.Counter`,
`dataclasses`, `datetime`, `typing`, `pandas`, `openpyxl.styles`, and
`department_normalizer`). The Excel export uses `pandas.ExcelWriter(engine="openpyxl")`
purely in-memory (`io.BytesIO`), the same pattern already used by
`demo_company_generator.py`'s `generate_bytes()`
([line 328](backend/core/demo_company_generator.py#L328)) — no temp files, no external
service calls.

This is backed by a real, already-installed platform-wide enforcement mechanism, not
just a promise: `backend/core/offline_mode_guard.py` patches `socket` and
`urllib`/`requests`/`httpx` at process start (installed via
`local_enterprise_runtime.py:37`) and raises `OfflinePolicyViolation` on any attempted
external connection, anywhere in the process. Any accidental network call added to this
module in the future would fail loudly, not silently succeed. The module docstring
([lines 4-9](backend/core/job_pattern_grouping_engine.py#L4-L9)) states this explicitly,
and the "no internet search" statement is repeated on-screen, unconditionally, at the top
of the frontend page (verified live in §5) — not just buried in the export.

## 4. Test results

`tests/test_job_pattern_grouping_engine.py` — **15/15 passed**:

```
$ python -m pytest tests/test_job_pattern_grouping_engine.py -v
...
15 passed in 0.76s
```

Coverage:
- **Title normalization** (3 tests): "Manager"/"manager"/"مدير" merge into one
  canonical key; "Sales Executive" vs. "Sales Exective" (typo) confirmed as two distinct
  keys, flagged together as an unmerged near-duplicate; the engine's disclosure notes
  contain both the merge and the review flag.
- **Hand-computed salary** (2 tests): the merged Manager pattern (salaries
  10000/12000/14000) computes avg=12000, median=12000, min=10000, max=14000 exactly; a
  missing `YearsAtCompany` value produces its own `experience_bucket=None` pattern
  rather than being dropped or guessed, distinct from a real 4-year value's "Mid-Level"
  pattern.
- **Honest partial-capability** (2 tests): a fixture with job title + department + salary
  but **no experience column at all** still groups correctly (by the 2 available
  dimensions), `columns_detected["experience"] is False`,
  `"experience" not in grouping_dimensions_used`, and the narrative text discloses the
  missing dimension — salary computation is unaffected by the missing dimension.
- **"Not detected"** (3 tests): `succession_test_data.csv` and `nitaqat_test_data.csv`
  (neither has a job-title column) correctly report `available: false`; the
  `unavailable_job_pattern_result()` factory never fabricates a pattern.
- **Real-fixture positive case** (2 tests): `test_employee_data.csv`'s real `JobRole`
  column (200 rows) correctly detected alongside `Department`, `YearsAtCompany`, and
  `MonthlyIncome`, producing genuine grouping (200 employees → 20 patterns, not 1:1);
  round-trip dict serialization (`job_pattern_grouping_to_dict` →
  `job_pattern_grouping_from_dict`) preserves every pattern's values exactly — this
  round-trip is what the `/export` route relies on.
- **Excel export PII safety** (3 tests): the exported workbook's every cell across both
  sheets was scanned and confirmed to contain **none** of the fixture's raw
  `EmployeeID` values; the "Job Patterns" sheet has exactly the 8 columns the brief
  specified, in order; patterns with fewer than
  `MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE` (3) employees correctly show
  `"Suppressed (n<3)"` instead of a salary figure.

## Full regression suite

```
$ python -m pytest tests/ -q
40 failed, 1410 passed, 1 skipped, 205 warnings in ~53s
```

1410 passed = the 1395 baseline after Phase 18 + 15 new Phase 19 tests. Same 40
pre-existing, unrelated failures (`test_phase29_extended.py`'s CEO dashboard tests and
`test_phase30_1_security.py`'s auth/bcrypt tests) — **zero regressions**.

## 5. Live browser verification

Backend restarted (no auto-reload) to pick up the two new routes; frontend restarted
after adding the page/nav entry. `npx tsc --noEmit` passed with zero errors before
verification. Same stale, unowned `127.0.0.1:8000` socket noted in the Phase 18 report
was still present on this machine — worked around identically (verified the real backend
via its `192.168.100.2:8000` LAN binding, temporarily pointed the Vite dev proxy there
for this verification session only, reverted immediately after — no net change to
committed config).

**Screenshot 1 — nav entry + upfront "no internet" statement**: "Job Pattern Grouping"
appears directly below "Recruitment Pipeline" in the sidebar (the thematic placement the
brief requested). The page's very first content banner states, unconditionally and
before any upload: *"This tool does NOT search the internet, contact any job board, or
call any AI service itself... Zero data leaves your machine."*

**Screenshot 2 — real pattern table from `test_employee_data.csv`**: uploaded the real,
existing 200-row fixture (no synthetic data needed here — it already has `JobRole`,
`Department`, `YearsAtCompany`, `MonthlyIncome`). Rendered live: 200/200 employees
grouped into 20 patterns using `job_title, department, experience` (JobLevel correctly
absent and disclosed), narrative text matching the engine's output exactly, and a sorted
table (Engineer/Engineering/24 employees/SAR 15.4K avg at the top) matching the
independently-verified smoke-test numbers from §1 exactly.

**Screenshot 3 — salary suppression visible on screen**: scrolled further down the same
table — two small patterns (Manager/Sales/2 employees and Specialist/Finance/1 employee)
correctly show a `"Suppressed (n<3)"` badge instead of a salary figure, matching the
governance note directly below: *"Patterns with fewer than 3 employees with a valid
salary value have their salary figures suppressed..."*

**Actual downloaded Excel file, inspected directly** (Playwright's `download` event,
saved and read back with `pandas.read_excel`): the file downloads with the exact
suggested filename `Job_Pattern_Market_Research_Worksheet.xlsx` and contains exactly two
sheets:
- **Instructions** (6 rows): the "What this is" / "What this is NOT" / "How to use it"
  guidance the brief specified verbatim, including the example prompt: *"What is the
  typical Riyadh salary range for a mid-level Sales Executive with 3-5 years
  experience?"*
- **Job Patterns** (20 rows): exactly the 8 columns specified — Pattern ID, Job Title
  (normalized), Level, Department, Experience Range, Employee Count, Current Avg Salary
  (SAR), Current Salary Range (SAR) — populated with the same real computed values shown
  on screen (e.g. P001 = Engineer / Engineering / 11-20 years / 24 employees / SAR
  15,363.62 / 7,377-23,863). `Level` is correctly blank (NaN) throughout, since
  `test_employee_data.csv` has no `JobLevel` column — no fabricated value.

Zero console errors or page errors across the full flow, including the file-download
step (`page.on('console')` and `page.on('pageerror')` both empty).

## Files changed

- `backend/core/job_pattern_grouping_engine.py` (new, ~610 lines — analysis, title
  normalization, and Excel export co-located; kept as one file rather than splitting
  out a separate exporter module, since the export logic is a ~90-line direct
  serialization of the same result dataclass, unlike the much larger
  `executive_pptx_exporter.py`/`executive_pdf_exporter.py` that justify their own files)
- `tests/test_job_pattern_grouping_engine.py` (new, 15 tests)
- `job_pattern_title_test_data.csv`, `job_pattern_no_experience_test_data.csv` (new
  fixtures, repo root)
- `backend/api/local_analysis_routes.py` (+7 lines import,
  [+2 routes, lines 2465-2596](backend/api/local_analysis_routes.py#L2465-L2596):
  `/job-pattern-grouping` for on-screen analysis,
  `/job-pattern-grouping/export` for the .xlsx download — the same
  analyze-then-export two-step pattern already used by `/export/pptx` and
  `/export/pdf`, so the raw dataset never needs to be re-uploaded for export)
- `executive-ui/src/pages/JobPatternGroupingTracker.tsx` (new)
- `executive-ui/src/types/index.ts` (+1 NavPage variant: `jobpatterns`)
- `executive-ui/src/App.tsx` (+2 lines: import + route case)
- `executive-ui/src/layout/Sidebar.tsx` (+1 icon import, +1 nav item, placed directly
  after Recruitment Pipeline)
