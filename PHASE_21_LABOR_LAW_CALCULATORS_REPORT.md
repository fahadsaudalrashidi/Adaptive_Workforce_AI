# Phase 21 — Saudi Labor Law Calculators (Gratuity, WPS Consistency, Leave Balance)

Three related, offline Saudi labor-law calculators built in one module
(`backend/core/labor_law_calculators.py`): End-of-Service Gratuity (Articles 84/85/87),
a WPS/Payroll internal consistency pre-check, and Leave Balance & Compensation
(Articles 109/111). Unlike every prior illustrative module this session, these compute
**real legally-owed amounts** — the central discipline verified throughout this phase is
that none of the three ever substitutes an estimate for a missing real number.

## 1. Part 0 investigation result

`saudi_data_governance.py` — the file named in the original brief — contains **no
gratuity calculation logic at all**. Its "termination"/"separation" references
([lines 108-123](backend/core/saudi_data_governance.py#L108-L123)) are PII/data-leakage
field-detection entries (flagging post-outcome fields like `termination_reason` as
leakage risks), unrelated to Article 84 math.

`financial_intelligence_engine.py` DOES contain real, correctly-cited base-formula
constants:
```python
# Saudi Labour Law — End-of-Service Gratuity multiplier (Art. 84)
ESG_SHORT_TENURE_PER_YEAR = 0.5   # months salary, years 1-5
ESG_LONG_TENURE_PER_YEAR  = 1.0   # months salary, years 6+
```
([`backend/core/financial_intelligence_engine.py:150-152`](backend/core/financial_intelligence_engine.py#L150-L152)),
already cross-imported and used by `executive_roi_engine.py:50-51,326-331` — but only
for a **portfolio-level average-tenure ROI exposure estimate** built on a sector/
seniority *benchmark* salary (illustrative board-level "at-risk liability" sizing), with
**no implementation of Article 85's resignation reduction tiers at all**. There is no
per-employee, per-department gratuity calculator anywhere in the codebase.

**Conclusion, and what was built on vs. built fresh**: the two base-formula constants
are imported directly and reused unchanged
([`labor_law_calculators.py:190-193`](backend/core/labor_law_calculators.py#L190-L193))
— real reuse, not reimplementation, following the exact cross-import precedent
`executive_roi_engine.py` already established for these specific public constants.
Everything else — per-employee calculation, Article 85 resignation tiers, Article 87
scope, WPS consistency, and Leave Balance/Compensation — was built fresh, since none of
it existed.

## 2. Current legal provisions confirmed via live search

**Article 84 (base formula)**: half a month's wage per year for the first 5 years, a
full month's wage per year thereafter, prorated for partial years, on the worker's last
actual wage. Confirmed via two independent sources.

**Article 85 (resignation reduction tiers)** — exact text retrieved: *"If the work
relation ends due to the worker's resignation, the worker shall... be entitled to
one-third of the award after a service of not less than two consecutive years and not
more than five years, to two-thirds of the award if his service is more than five
consecutive years but less than ten years, and to the full award if his service is ten
years or more."* i.e. <2y=none, 2-5y=1/3, 5-10y=2/3, 10y+=full — matches the brief's
stated tiers exactly, now backed by the article's own text rather than assumed current.

**Article 87 (full-award exceptions)**: force majeure beyond the worker's control, or a
female worker ending her contract within 6 months of marriage / 3 months of childbirth.
**Deliberately not computed by this module** — the underlying reason for separation is
not reliably present in typical HR export data, so Article 87 eligibility is never
guessed (disclosed in `GRATUITY_SOURCES`,
[`labor_law_calculators.py:280-285`](backend/core/labor_law_calculators.py#L280-L285)).

**Wage base — a real correction to the brief's own draft language**: the brief describes
the base as "final basic wage," but every source retrieved describes it as the worker's
**"last actual wage"** — basic salary *plus* regular fixed allowances/commissions — not
basic salary alone. This module cannot know whether a detected salary column already
includes allowances, so it computes on whatever numeric column is detected and discloses
that column's exact name in every result rather than claiming to have used "total wage"
([module docstring, lines 60-68](backend/core/labor_law_calculators.py#L60-L68)).

**Article 109 (annual leave entitlement)**: 21 days/year for the first 5 years, 30
days/year thereafter — confirmed current.

**Article 111 (compensation for unused leave)**: daily wage = actual monthly wage ÷ 30;
compensation = daily wage × unused leave days. The divisor-30 convention was
specifically confirmed (not assumed) via a worked example in the retrieved source
(6,000 SAR monthly → 200 SAR/day → 2,000 SAR for 10 unused days).

Sources (retrieved via live web search this phase):
- [Article 84 Saudi Labor Law: Guide To Gratuity Calculations](https://etqanlawfirm-sa.com/en/article-84-saudi-labor-law/)
- [Saudi EOSB Entitlement: Resignation Tiers (Art 85) & Full Award](https://saudieosbcalculator.com/entitlement/)
- [How to Calculate End of Service Benefits (Gratuity) in KSA](https://payrollmiddleeast.com/how-to-calculate-end-service-benefits-in-ksa/)
- [Article 111 Of The Saudi Labor Law: Workers' Rights, Compensation, And Calculation Of Wages And Unused Leave](https://alothmanlaw.sa/en/article-111/)
- [Article 109 Saudi Labor Law: Employee Leave Rights & Benefits](https://etqanlawfirm-sa.com/en/article-109-saudi-labor-law/)
- Additional corroborating results from the live search rounds (qureos.com, ksaexpats.com,
  jisr.zendesk.com, cercli.com) cross-checked the same figures — no conflicting provisions found.

## 3. The strict numeric-salary-only rule — implementation and verification

`_extract_strict_numeric_salary()`
([`labor_law_calculators.py:262-303`](backend/core/labor_law_calculators.py#L262-L303))
is the shared utility all three calculators use: `pd.to_numeric(errors="coerce")` per
row; a row's wage is used **only** if it parses to a positive number, otherwise it is
excluded and counted, with one example raw excluded value preserved for the UI (a
data-shape example, not PII — e.g. `'From 5000 to 10000 S.R'`). This is the deliberate
opposite of `financial_intelligence_engine.estimate_monthly_salary()`'s fallback chain
(which substitutes a sector/seniority benchmark), documented explicitly in the module
docstring as the reason this module is stricter.

**A second, equally important precision fix specific to the legal stakes**: the real
attrition dataset has *two* experience-shaped columns — `Years_Experience` (total career
experience, any employer) and `Years_experience_lastorganization` (tenure at the current
employer). End-of-Service Gratuity is legally computed on tenure at the current employer,
not total career experience — using the wrong one would produce a materially wrong legal
figure. `_YEARS_OF_SERVICE_PATTERNS`
([`labor_law_calculators.py:113-121`](backend/core/labor_law_calculators.py#L113-L121))
is deliberately narrower than `job_pattern_grouping_engine.py`'s experience pattern,
written to match `Years_experience_lastorganization` (via its `...last organi[sz]ation`
suffix) while NOT matching a bare `Years_Experience`-style column. **Verified against the
real dataset**: `analyze_gratuity()` correctly selected `'Years_experience_lastorganization'`,
never the wrong `'Years_Experience'` column (confirmed in the live screenshot, §5).

**Verified against real range-text data** (the exact case Phase 20 found): on the real
1,191-row Original Dataset of Employee Attrition, `MonthlySalary` is 100% range-text
("From 5000 to 10000 S.R") and `Years_experience_lastorganization` is 100% range-text
("Less than 5 years") — both correctly produce `available: False` with the specific
detected column names and an example bad value cited, never an approximated figure. This
is the live-verified "critical screenshot" (§5).

**Mixed-data behavior also verified** (not just all-or-nothing): a synthetic 3-row
fixture with 2 clean salaries and 1 range-text value correctly computes real figures for
the 2 clean rows and excludes+counts the 1 bad row
(`test_gratuity_partial_range_text_excludes_only_bad_rows`) — the strict rule degrades
per-row, not per-dataset, so a mostly-clean upload still produces real, useful figures.

## 4. Part 2 (WPS consistency) — logic and real-fixture findings

Detects two column roles: `_CONTRACT_BASIC_SALARY_PATTERNS` (contract/basic/base salary)
and `_ACTUAL_PAID_SALARY_PATTERNS` (actual-paid/net/total/gross salary), plus an optional
`_ALLOWANCES_PATTERNS` column
([`labor_law_calculators.py:129-140`](backend/core/labor_law_calculators.py#L129-L140)).
Two reconciliation modes:
- **Two-column**: contract/basic vs. actual/total, flagged when they diverge beyond
  `max(SAR 10, 1% of basic)` — an illustrative practical tolerance (documented as such,
  not a legal or WPS-system-defined threshold), the same kind of judgment call as this
  session's other numeric thresholds (e.g. `contract_expiry_engine.py`'s 30/60/90-day
  tiers).
- **Three-column**: when allowances is also present, checked as basic + allowances ≈
  total instead of basic ≈ total directly (verified in
  `test_wps_three_way_base_plus_allowances_vs_total`).

**Honest "not applicable" is the default, verified case**: `test_employee_data.csv`
(one salary column, `MonthlyIncome`) and — more importantly — the real Original Dataset
of Employee Attrition both correctly report `check_applicable: False`. The real dataset
was a genuinely interesting case: it has an `Allowances` column (matching
`_ALLOWANCES_PATTERNS`) but no distinct contract/basic *and* actual/total pair, so the
check correctly still reports not-applicable rather than trying to reconcile with only
half the needed columns — live-verified in §5.

**On the dedicated synthetic mismatch fixture** (`labor_law_wps_test_data.csv`, 5
employees): 2 real mismatches found (40%) — a −2,000 SAR drift (contract 8,000 vs. actual
6,000) and a +500 SAR drift (contract 10,000 vs. actual 10,500) — while a 5 SAR
difference on a third employee correctly stayed under the tolerance and was NOT flagged.
Confirmed identically in both the automated test and the live browser screenshot (§5).

## 5. Test results

`tests/test_labor_law_calculators.py` — **26/26 passed**:

```
$ python -m pytest tests/test_labor_law_calculators.py -v
...
26 passed in 0.58s
```

Coverage: every Article 85 resignation tier hand-computed (0%, 1/3, 2/3, full) including
the year-5 boundary inside the base Article 84 formula itself; lowercase/alternate
separation-type token classification; employer-termination always full award regardless
of tenure; unspecified-separation showing both scenarios distinctly; department rollup
proving real `department_normalizer.py` reuse (`"HR"` correctly normalizes to `"Human
Resources"` via that module's own curated table); range-text salary refusal (whole-dataset
and mixed-data partial-exclusion cases); leave entitlement across the 21-vs-30-day
boundary; Article 111 daily-wage-over-30 compensation formula; entitlement-only fallback
when no leave-balance/leave-taken column exists; WPS two-column and three-column
reconciliation; WPS not-applicable on a real single-salary-column fixture; and PII
safety (no raw employee ID appears anywhere in either calculator's serialized output).

## Full regression suite

```
$ python -m pytest tests/ -q
40 failed, 1445 passed, 1 skipped, 205 warnings in ~54s
```

1445 passed = the 1419 baseline after Phase 20 + 26 new Phase 21 tests. Same 40
pre-existing, unrelated failures — **zero regressions**.

## 6. Live browser verification

Backend/frontend restarted to pick up the new routes and page. `npx tsc --noEmit` passed
cleanly. Same stale `127.0.0.1:8000` socket noted in Phases 18-20 was still present —
worked around identically (temporary Vite proxy redirect for verification only, reverted
immediately after).

**Page load**: the "Saudi Labor Law Calculators" nav entry sits directly below Contract
Expiry & Renewal (both compliance-themed). The disclaimer banner renders in **critical
(red) tone** — visually distinct from every other module's softer informational
disclaimers, matching the brief's explicit request for more prominent framing here.

**Clean-data scenario** (`labor_law_clean_data_test.csv`, 7 employees, real numeric
salary): Gratuity tab shows real computed figures matching hand-calculations exactly
(e.g. 12 years/SAR 10K/resignation → SAR 95.0K full award, since 10+ years resignation =
full award under Article 85; 7 years/resignation → SAR 45.0K full, SAR 30.0K at the 2/3
resignation fraction). Leave Balance tab shows entitlement correctly crossing the 5-year
21-vs-30-day boundary (12 years → 315 days) with real compensation figures. WPS tab
correctly shows "not applicable" (this fixture, like most fixtures this session, has only
one salary column) — a separate screenshot against `labor_law_wps_test_data.csv`
confirms the "2 mismatches found (40%)" path with the exact SAR 500 and SAR −2,000
differences matching the test suite precisely.

**Critical screenshot — real range-text dataset, strict honesty enforced**: uploaded the
real 1,191-row Original Dataset of Employee Attrition directly. Gratuity tab: *"Gratuity
calculation not available... Found a salary column ('MonthlySalary') and a
years-of-service column ('Years_experience_lastorganization'), but no single employee row
had BOTH values as clean, usable numbers... Example unusable salary value from
'MonthlySalary': 'From 5000 to 10000 S.R'."* Both required columns show green checkmarks
(correctly detected), proving the failure is about unusable *values*, not missing
*columns* — exactly the distinction the strict-honesty framing promises. Leave Balance
tab shows the equivalent honest degradation for the same reason (years-of-service is
range-text on this dataset too). WPS tab correctly reports not-applicable (only one true
salary column despite an `Allowances` column also being present). Zero console or page
errors across every scenario tested.

## Files changed

- `backend/core/labor_law_calculators.py` (new, ~1,050 lines — three calculators + the
  shared strict-salary utility, kept in one file since all three share it; see module
  docstring for the full reasoning trail on every judgment call made this phase)
- `tests/test_labor_law_calculators.py` (new, 26 tests)
- `labor_law_clean_data_test.csv`, `labor_law_wps_test_data.csv` (new fixtures, repo root)
- `backend/api/local_analysis_routes.py` (+10 lines import, +3 routes: `/gratuity-calculator`,
  `/wps-consistency-check`, `/leave-balance-calculator`)
- `executive-ui/src/pages/SaudiLaborLawCalculators.tsx` (new — one page, tab-switched
  between the three calculators, sharing a single upload; reasoning for combining rather
  than three separate pages documented in the file's own header comment)
- `executive-ui/src/types/index.ts`, `App.tsx`, `layout/Sidebar.tsx` (+1 NavPage variant,
  routing, nav entry placed directly after Contract Expiry & Renewal)
