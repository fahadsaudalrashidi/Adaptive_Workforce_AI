# Phase 17 — Pay Equity Analysis + Urgent Nitaqat Qiwa Disclosure Fix

Status: **Complete. Part 1's regulatory claim independently verified via
live web search (official HRSD source found directly, plus Saudi Gazette
and a real immigration law firm, all converging on identical specifics) and
added, additively, to the Nitaqat disclaimer in both the API and the UI
banner, in both English and Arabic. Part 2 ships a new, genuinely real Pay
Equity engine, reusing Phase 6's statistical-testing and minimum-group-size
discipline rather than reimplementing it, wired end-to-end into a new
bilingual frontend page. Zero new regressions (1370 passed, same 40
pre-existing/unrelated failures as before this phase).**

---

## Part 1 — Nitaqat Qiwa contract-authentication disclosure

### Regulatory verification (independent, not taken on the user's summary)

Two live web searches plus a direct fetch of the strongest-looking primary
source, run before writing any code:

1. *"Qiwa contract authentication Nitaqat Saudization headcount April
   2026"* and *"Nitaqat Qiwa 'contract' 'authentication' requirement 2026
   HRSD Saudi Arabia"* — returned a consistent claim across many
   independent sources: effective **2026-04-15**, a Saudi employee's
   contract must be electronically documented **and authenticated** on
   Qiwa to count toward Nitaqat headcount — GOSI registration alone is no
   longer sufficient. Phased compliance targets: 85% documented by
   2026-04-30, 90% by 2026-06-30.
2. A follow-up search specifically for `site:hrsd.gov.sa OR site:qiwa.sa`
   surfaced the **official ministry page directly**:
   `hrsd.gov.sa/en/media-center/news/...` — titled "The Ministry of Human
   Resources and Social Development has mandated the electronic
   documentation of employment contracts through the 'Qiwa' platform." The
   page itself returned HTTP 403 on direct fetch (bot-blocked), so it
   could not be quoted verbatim, but its existence and title were
   confirmed independently via search, not just inferred from a
   secondary source.
3. `saudigazette.com.sa/article/659791` — Saudi Gazette (a legitimate
   English-language Saudi newspaper), "Saudi Arabia updates Nitaqat
   Saudization calculation through Qiwa contracts."
4. `eiglaw.com/saudi-arabia-saudization-updates-qiwa-contract-documentation-impacts-nitaqat-calculations`
   — Erickson Immigration Group, a real US immigration law firm, whose
   summary explicitly cites "MHRSD announcements from their media center"
   as its source and confirms the same effective date and the same 85%/90%
   phased targets independently.

Four independent sources (one official government page found directly, one
national newspaper, one law firm citing the same ministry announcement,
plus the original set of corroborating compliance-industry sources)
converging on identical, specific, falsifiable facts (exact date, exact
percentages) is well past this platform's "authoritative or multiply
corroborated" verification bar — this is not the same failure class as the
Nitaqat premium constant or the Age-disparity bug (those were fabricated
*numbers with no source at all*; this is a real, dated, government-issued
policy change, independently found, not merely asserted).

### What was changed

`backend/core/nitaqat_compliance_engine.py`:
- New constants `NITAQAT_QIWA_CONTRACT_NOTE_EN`/`_AR`
  (`nitaqat_compliance_engine.py:194-206`), appended — via string
  concatenation, not replacement — onto the existing
  `NITAQAT_ILLUSTRATIVE_DISCLAIMER_EN`/`_AR` constants
  (`nitaqat_compliance_engine.py:208-224`). The pre-existing "Illustrative
  estimate — NOT an official Nitaqat/HRSD determination... verify actual
  status via Qiwa" text is preserved **word-for-word**, unchanged.
- Module docstring updated (`nitaqat_compliance_engine.py:63-77`) with the
  full source citations, following this file's own established pattern of
  dating and citing every regulatory claim (matching the existing Phase 7
  band-name and small-establishment citations already in the same
  docstring).
- Since `disclaimer_en`/`disclaimer_ar` flow through
  `nitaqat_compliance_to_dict()` unchanged (`nitaqat_compliance_engine.py:501-502`),
  every consumer of the API response — including the frontend's
  post-analysis banner, which reads `nc.disclaimer_en` directly — picked
  up the new text automatically, with no separate frontend wiring needed
  for that instance.

`executive-ui/src/pages/NitaqatComplianceTracker.tsx:197-213` — the
**persistent, pre-upload** banner (shown before any file is uploaded, so
it can't read live API data) is hardcoded frontend text and was updated
separately, appending the identical new sentence after the existing
hardcoded disclaimer text, in both languages.

### New test

`tests/test_nitaqat_compliance_engine.py` — two new tests
(`test_available_result_discloses_qiwa_contract_authentication_gap`,
`test_unavailable_result_also_discloses_qiwa_contract_authentication_gap`)
asserting the new text is present (`"qiwa"`, `"contract authentication"`,
`"april 2026"` in English; `"قوى"`, `"أبريل 2026"` in Arabic) **and** that
the original "not an official" disclaimer text survives — additive, not a
replacement. All 32 tests in the file pass.

### Live verification (screenshots, `scratchpad/p17/`)

- `nitaqat_en_persistent_banner.png` — the pre-upload banner now reads, in
  full: *"...before any hiring, visa, or compliance decision. This
  estimate is based on nationality data only. Since April 2026, official
  Nitaqat counting also requires Qiwa contract authentication status,
  which this platform cannot verify — actual counted headcount may differ
  from this estimate."*
- `nitaqat_en_after_analysis.png` — real data
  (`nitaqat_realistic_multidept_test_data.csv`, 220 rows) uploaded, 61.4%
  Saudization / High Green band correctly computed, banner text intact.
- `nitaqat_ar_after_analysis.png` — Arabic mode, RTL layout correct, banner
  reads *"...اعتباراً من أبريل 2026، يتطلب الاحتساب الرسمي لنطاقات أيضاً
  حالة توثيق العقد عبر منصة قوى..."* appended after the original Arabic
  disclaimer. Zero console errors across the whole run.

---

## Part 2 — Pay Equity Analysis

### Methodology and reuse of Phase 6 (`ethical_ai.py`)

**Reused verbatim, not reimplemented:**
- `_detect_protected_attributes()` (`ethical_ai.py:169-206`) — called
  directly (`pay_equity_engine.py:88` import), then filtered to the
  gender/nationality/race/age types relevant to pay equity.
- `_MIN_GROUP_SIZE_FOR_DISPARITY` (=20, `ethical_ai.py:93`) — the exact
  same minimum-group-size floor, same constant, same reasoning (a
  comparison between two small groups is dominated by sampling noise).
- `_bucket_or_skip_for_disparity()` (`ethical_ai.py:264-328`) — the exact
  same high-cardinality guard. Confirmed live: Age (many distinct values)
  is quantile-bucketed into ranges like `(38.0, 44.4]` rather than compared
  on raw values — visible in `payequity_04_test_employee_data.png`'s
  second table row.
- `_SIGNIFICANCE_ALPHA` (=0.05, `ethical_ai.py:95`) — same threshold for
  the significant/not-significant verdict.

**Genuinely new, not reused — and deliberately so:** `ethical_ai.py`'s
`_two_proportion_z_test()` compares two *rates* (e.g. attrition rate
between groups). Pay equity compares two *means* of continuous salary
data — applying a proportion test there would be statistically wrong, not
mere reuse. `pay_equity_engine.py:_welch_t_test()`
(`pay_equity_engine.py:172-190`) implements Welch's unequal-variance
two-sample t-test instead — the correct test for this comparison shape —
following the identical discipline as its Phase 6 counterpart (scipy
optional-import guard, returns `None` rather than ever fabricating a
p-value, same reused `_SIGNIFICANCE_ALPHA`).

`department_normalizer.py`'s `normalize_department_series()` is reused
verbatim for department-level grouping (`pay_equity_engine.py:391-401`),
identical to every other module this session.

### Comparability cohorts — a bug caught and fixed during my own development

Initial design: split each Job Level by Department only if a majority of
that level's raw department cells individually cleared the 20-person
floor. Live-tested against a 400-row realistic fixture, this **fragmented
large, evenly-spread job levels into department cells that then failed the
floor a second time once further split by gender** — discarding a sample
(Job Level 1: 110 people) that was in fact plenty large for a whole-level
comparison, while smaller, correctly-fragmented levels fell through to the
right behavior. Root cause: checking department-cell size without
accounting for the protected attribute's own split. Fixed
(`pay_equity_engine.py:267-295`) to decide the department-vs-job-level
question **empirically** — try department cohorts first; fall back to the
whole job level only if the department split produces zero cohorts with
2+ groups actually clearing the floor. Re-verified: the 400-row fixture
now correctly produces 4 usable job-level-wide comparisons instead of 0.

### Honest degradation

Missing salary, missing protected attribute, or missing both comparability
factors (JobLevel *and* Department) each return `available: false` with a
specific `reason` and a `columns_detected` dict — rendered via the same
`EmptyState` component every other module uses
(`PayEquityTracker.tsx:255-264`). Confirmed against
`succession_test_data.csv` (has JobLevel + Nationality, no salary column
at all) — correctly unavailable, `columns_detected.salary_or_compensation
== False`.

### Tests (`tests/test_pay_equity_engine.py`, 15 tests, all passing)

- Real computed-value assertions: `pay_equity_realistic_test_data.csv` (a
  new, purpose-built 400-row fixture — no existing fixture combined
  MonthlyIncome + Gender + JobLevel + Department at adequate scale) — gaps
  and p-values are **independently recomputed from the CSV via pandas +
  scipy inside the test file** and compared exactly against the engine's
  output, for both a statistically significant cohort (Job Level 4: 11.3%
  gap, p<0.0001) and a non-significant one (Job Level 1: 1.5% gap,
  p=0.397) in the same dataset.
- Minimum-group-size suppression: 25 vs 8 people → suppressed, counted,
  never reported. Exactly-at-the-boundary (20 vs 20) → correctly *not*
  suppressed.
- High-cardinality bucketing: Age with many distinct values → bucketed,
  matching `ethical_ai.py`'s guard.
- Four "not detected" tests (missing salary / missing protected attribute
  / missing comparability factor / a real fixture genuinely lacking
  salary).
- Department-only comparability (no JobLevel at all) — confirmed working,
  since the spec allows either factor alone.
- Department-fallback-to-job-level behavior on the real 400-row fixture.
- JSON-safety and disclaimer-presence checks, matching this codebase's
  established test-suite conventions.

One bug in my own test (not the engine) was caught and fixed during this
process: an early version of the independent-recomputation helper assumed
"Male minus Female" as a fixed direction, which produced the wrong sign at
Job Level 1 (where Female happened to be the higher-paid group that
cohort) — fixed to match the engine's actual "higher minus lower,
whichever group really pays more" convention before trusting the
assertion.

### Live wiring

- `backend/api/local_analysis_routes.py` — new `POST /api/local/pay-equity`
  route (`local_analysis_routes.py:1819-1926`), modeled on the simpler
  `/overtime-cost-intelligence` pattern (no ML-scoring dependency needed).
  **Required a backend process restart to register** — the server runs
  with `reload=False` (`main.py:415`), so route additions don't hot-reload
  like the Vite frontend does. Restarted cleanly; confirmed via direct
  `curl` before touching the browser.
- `executive-ui/src/pages/PayEquityTracker.tsx` — new bilingual page,
  built on the same shared components as every other Phase 14/15 page
  (`StatusBanner`/`StatusBadge`/`StatusLegend`, `KPICard`, `EmptyState`,
  `useSortableTable` + `SortToggle`, `row-hover-card` table styling) —
  zero new UI patterns invented.
- Nav: added `'payequity'` to `NavPage` (`types/index.ts:173`), a new
  Sidebar entry (`Sidebar.tsx:173-181`) placed directly after Fairness/Bias
  Audit and before Nitaqat, matching the requested "grouped near
  Fairness/Bias Audit" placement, with a new `Coins` icon (distinct from
  Payroll's `Wallet` and Fairness's `Scale`).

### Live verification (screenshots, `scratchpad/p17/`)

- `payequity_02_realistic_results.png` — 400 real rows, 4 comparisons
  computed, 2 significant (50% shown on the hero ring), 1 suppressed for
  small sample. Table shows real cohort labels, real group means in SAR,
  real gap %, real p-values, and correct `Significant`/`Not Significant`
  badges (critical-red vs. neutral-gray, per Phase 15's status-tone
  system).
- `payequity_03_sorted.png` — "Gap %" sort toggle confirmed interactive.
- `payequity_04_test_employee_data.png` — the **real, unmodified**
  `test_employee_data.csv` (200 rows, Department-only comparability, no
  JobLevel) — genuinely found a real 19.7% significant gap in Engineering
  (p=0.039) and correctly bucketed Age into quantile ranges.
- `payequity_05_arabic.png` — full Arabic/RTL rendering confirmed correct,
  including the sortable table and all disclosure banners.
- **Zero console errors** across every run.

---

## Regression suite

`python -m pytest tests/ -q`:

**Before this phase's changes were exercised again (Phase 16 baseline):**
1353 passed, 40 failed, 1 skipped.

**After Part 1 + Part 2:** **1370 passed**, 40 failed, 1 skipped — the
increase of 17 is exactly the 2 new Nitaqat tests + 15 new pay-equity
tests, all passing. The 40 failures are the identical, pre-existing,
unrelated set confirmed in Phase 16 (39 from a missing `bcrypt` package in
the venv, 1 stale test asserting on `WorkforceHealthWheel`, a component
removed in Phase 12) — unchanged in count, unchanged in identity, nothing
newly broken.

`npx tsc --noEmit` clean after every frontend edit.

## Files changed

`backend/core/nitaqat_compliance_engine.py`,
`executive-ui/src/pages/NitaqatComplianceTracker.tsx`,
`tests/test_nitaqat_compliance_engine.py` (Part 1);
`backend/core/pay_equity_engine.py` (new),
`tests/test_pay_equity_engine.py` (new),
`pay_equity_realistic_test_data.csv` (new fixture),
`backend/api/local_analysis_routes.py`,
`executive-ui/src/pages/PayEquityTracker.tsx` (new),
`executive-ui/src/types/index.ts`,
`executive-ui/src/layout/Sidebar.tsx`,
`executive-ui/src/App.tsx` (Part 2).
