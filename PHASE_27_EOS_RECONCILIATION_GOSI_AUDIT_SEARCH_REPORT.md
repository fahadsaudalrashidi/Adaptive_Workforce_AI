# EOS Reconciliation, GOSI Re-Audit, Employee ID Search

Three priorities: reconcile Gratuity/Leave against the user's authoritative
`Copy of EOS Report.xlsx`, independently re-audit the GOSI Calculator, and add
employee ID search across every per-employee table. Internally labeled "Phase 39/40"
in code comments (continuing this session's running counter); filename follows the
brief's own naming.

## Priority 1 — Excel reconciliation

### Method

`Copy of EOS Report.xlsx` was opened with `openpyxl` twice — once with
`data_only=False` to read the literal formula strings, once with `data_only=True`
to read the cached computed values — and every non-empty cell across all 7 sheets
(`نموذج يدوي`, `نهاية الخدمة`, `EOS C`, `New`, `Sheet1`, `Gosi`, `Sheet3`) was
dumped for inspection (a temporary UTF-8 dump file, deleted after analysis).

### Findings: base formula and leave compensation — exact match, no bug

The workbook's own gratuity formula, present identically in all 4 populated
gratuity sheets:

```
=IF(TotalWorkingDays<=1825, (Salary*0.5)*Years, ((Salary*0.5)*5)+(Salary*(Years-5)))
```

is **exactly** `labor_law_calculators._base_gratuity_sar()`
([labor_law_calculators.py:423-429](backend/core/labor_law_calculators.py#L423-L429)):
`wage*years*0.5` for years≤5 (1825 days = 5×365), else `wage*5*0.5 + wage*(years-5)*1.0`.
Three of the workbook's own real worked examples were reproduced bit-for-bit (to
float rounding):

| Sheet | Salary | Years | Excel base EOS | Platform output |
|---|---|---|---|---|
| نهاية الخدمة (Amal Alshamry) | 11,081 | 5.120547945205479 | 29,038.291780821917 | **29,038.29** |
| EOS C (exact 5.0-year boundary) | 7,000 | 5.0 exactly | 17,500.0 | **17,500.00** |
| New | 10,425 | 3.863013698630137 | 20,135.95890410959 | **20,135.96** |

The Article 85 resignation-tier fraction multipliers (0 / 1/3 / 2/3 / full) matched
too — e.g. "نهاية الخدمة"'s F23 = `E23*F12` (F12 = 2/3, since 5.12 years falls in the
5-10y tier) = 19,358.861187214592, and "New"'s I13 = `I15*G13` (G13 = 1/3, since 3.86
years falls in the 2-5y tier) = 6,711.986294657877 — both reproduced exactly (§ live
verification table below). Leave compensation (`salary/30*days`, Article 111) also
matched exactly: EOS C's `D19 = D13/30*B19 = 7000/30*18 = 4200` and "نهاية الخدمة"'s
`F22 = E15/30*C22 = 11081/30*60 = 22162` both reproduced exactly.

**Conclusion: Articles 84/85/111 were already correctly implemented before this
phase — the reference file confirms it, it does not correct it.**

### The one real discrepancy: "Termination (80)" was silently treated as ordinary termination

The workbook's own "Type" selector (sheet `نموذج يدوي` cell K10-K12, sheet
`نهاية الخدمة` cell I10-I12) lists **three** separation types: `Resignation`,
`Termination (80)`, `EndOfContract` — not two. The prior code's `_TERMINATION_TOKENS`
set only recognized generic termination language and would have silently absorbed
"Termination (80)" into the same full-award bucket as ordinary termination via a
substring match on `"termination"`.

Live research (2 independent searches, both corroborating each other and multiple
secondary law-firm sources) confirms this is not a synonym: **Saudi Labor Law Article
80** lets an employer dismiss a worker for one of 9 specific for-cause grounds (serious
misconduct, dishonesty, assault, unauthorized absence, etc.) **without notice, gratuity,
or indemnity** — a real forfeiture, distinct from ordinary termination (redundancy,
restructuring, contract completion), which still owes the full award. Multiple sources
(traced to a common Lexology-published lineage — not a directly-quoted statute excerpt,
unlike Articles 84/85) further describe an Article 87 exception preserving **half** the
award for workers with 5+ years of service even under an Article 80 dismissal.

**Fix** ([labor_law_calculators.py:129-146](backend/core/labor_law_calculators.py#L129-L146),
[233-256](backend/core/labor_law_calculators.py#L233-L256)): added `_ARTICLE_80_TOKENS`
(`"termination (80)"`, `"article 80"`, `"dismissal for cause"`, `"المادة 80"`, etc.),
checked in `_classify_separation_type()` **before** the generic termination fallback
(since "Termination (80)" itself contains the substring "termination"). A new
`GratuityCandidate.article_80_reduced_award_sar` field discloses the possible
forfeiture (0 if years<5, half the full award at 5+ years) as an **additional** data
point — `applicable_amount_sar` is **never** auto-reduced, since (a) this provision is
less certainly sourced than Articles 84/85 and (b) actual forfeiture legally requires
verified compliance with Article 80's specific grounds and procedure, which no bare
text classification can confirm. This mirrors the exact same discipline Phase 21
already established for Article 87 (never guessed from data alone).

### Test results

```
$ py -m pytest tests/test_eos_report_excel_reconciliation.py -v
...
10 passed in 0.53s
```

New `tests/test_eos_report_excel_reconciliation.py`: 5 tests directly reproducing the
Excel's own worked examples (base formula at both tenure bands, the exact 5.0-year
boundary, resignation-tier fractions, fractional leave-day compensation) + 5 tests for
the Article 80 addition (detection, the two forfeiture-amount cases, confirming
ordinary "Termination" is unaffected, dict serialization).

### Live verification — side-by-side, Excel vs. running platform

`eos_report_reconciliation_test_data.csv` (5 rows built from 3 of the workbook's real
worked examples + 2 new synthetic Article 80 cases) POSTed to the live
`/api/local/gratuity-calculator` and `/api/local/leave-balance-calculator` endpoints:

| Employee (source) | Excel figure | Platform output |
|---|---|---|
| Amal Alshamry (نهاية الخدمة), applicable | SAR 19,358.86 | **SAR 19,358.86** |
| EOS C employee, base (5.0y boundary) | SAR 17,500.00 | **SAR 17,500.00** |
| New-sheet employee, applicable (1/3 tier) | SAR 6,711.99 | **SAR 6,711.99** |
| Amal Alshamry, leave compensation | SAR 22,162.00 | **SAR 22,162.00** |
| EOS C employee, leave compensation | SAR 4,200.00 | **SAR 4,200.00** |
| New-sheet employee, leave compensation | SAR 9,524.975 | **SAR 9,524.98** |
| Synthetic, Art. 80, 3y service | full 13,500.00 / reduced 0.00 | **full 13,500.0 / reduced 0.0** |
| Synthetic, Art. 80, 8y service | full 49,500.00 / reduced 24,750.00 | **full 49,500.0 / reduced 24,750.0** |

Every figure matches exactly. `SaudiLaborLawCalculators.tsx`'s Gratuity tab was also
updated to surface the Article 80 case live: a new "If Article 80 Applies" column, a
critical-tone banner explaining the never-auto-reduced discipline, and a new
"Art. 80 (for cause)" badge distinct from the existing "Termination" badge — confirmed
in a live browser screenshot (§ Priority 3 verification also captures this page).

## Priority 2 — GOSI re-audit: no discrepancy found

### Independent re-verification (3 fresh live searches, separate from Phase 25/37)

- Search 1 (general rates): confirmed Old System 21.5% (9.75% employee / 11.75%
  employer), New System 23.5% as of the current period (10.75% employee / 12.75%
  employer, effective 1 July 2026), non-Saudi 2% employer-only / 0% employee.
- Search 2 (subject wage): confirmed base = basic salary + housing allowance only
  (transport/phone/commission/bonus excluded), cap SAR 45,000/month, applying
  identically to non-Saudi employer contributions.
- Search 3 (worked-example calculator): broadly corroborated the same rate structure
  (one aggregator's SAR 20,000 example showed internally-inconsistent arithmetic that
  double-counted the SANED component — flagged as a low-quality source and
  disregarded in favor of the two higher-quality, mutually-consistent searches above).

**All three fresh searches confirm the exact rate constants already in
`gosi_calculator_engine.py`** — no change to `OLD_SYSTEM_EMPLOYEE_RATE` (0.0975),
`OLD_SYSTEM_EMPLOYER_RATE` (0.1175), `NEW_SYSTEM_EMPLOYEE_RATE` (0.1075),
`NEW_SYSTEM_EMPLOYER_RATE` (0.1275), `NON_SAUDI_EMPLOYER_RATE` (0.02), or
`GOSI_WAGE_CAP_SAR` (45000.0) was needed.

### Hand-computed worked examples vs. live engine output

Four scenarios, chosen to specifically exercise the bug classes named in the brief
(cap application base, current-period rate selection, employee/employer double-counting):

| Scenario | Hand-computed | Engine output |
|---|---|---|
| Saudi, Old System, 10,000 salary + 2,000 housing = 12,000 wage | employee 1,170.00 / employer 1,410.00 | **1,170.0 / 1,410.0** |
| Saudi, New System, 30,000 + 8,000 = 38,000 wage | employee 4,085.00 / employer 4,845.00 | **4,085.0 / 4,845.0** |
| Saudi, unspecified system, 40,000 + 10,000 = 50,000 raw → **capped to 45,000** | old total 9,675.00 / new total 10,575.00 | **9,675.0 / 10,575.0** |
| Non-Saudi, 25,000 + 5,000 = 30,000 wage | employee 0 / employer 600.00 | **0.0 / 600.0** |

All four matched exactly, including the specific cap-mechanics check: the SAR 45,000
cap is correctly applied to the **combined** basic+housing figure (50,000 → 45,000),
not to basic salary alone, and not skipped. No double-counting between employee/employer
shares was found (each pair sums to exactly `subject_wage × total_rate`).

### Conclusion

**No discrepancy was found after this re-audit.** Both the rates and the
implementation mechanics (cap base, current-period selection, employee/employer
split) check out against 3 independent fresh sources and 4 hand-verified scenarios
directly run against the live engine. No code change was made to
`gosi_calculator_engine.py`'s calculation logic. The 4 scenarios above are now a
permanent regression test (`TestPhase40IndependentReaudit` in
`tests/test_gosi_calculator_engine.py`, 4 tests, all passing) so this specific audit
can't silently regress. **Per the brief's own instruction: since no bug could be
identified despite this thorough process, the user is asked for the specific
employee/scenario where incorrect output was observed** — without a concrete example,
there is nothing further to fix, and claiming a fix without evidence would itself be
dishonest.

## Priority 3 — Real employee ID display + search

### Audit: which modules show `record_id_safe` vs. a real identifier

| Module | Before | Per-employee rows? |
|---|---|---|
| Gratuity / WPS / Leave Balance (`SaudiLaborLawCalculators.tsx`) | hash | yes |
| Contract Expiry (`ContractExpiryTracker.tsx`) | hash | yes |
| GOSI (`GosiCalculator.tsx`) | hash | yes |
| Succession Readiness (`SuccessionReadinessTracker.tsx`) | hash | yes |
| Employee Risk Dashboard (`EmployeeRiskDashboard.tsx`) | hash | yes — **has a real "Export CSV" download** |
| HR Letter Generator | real name + real ID (by design) | yes |
| Pay Equity, Fairness Audit | n/a | **no** — cohort/group-level tables only, no per-employee rows at all |
| Payroll Movements, Overtime Cost Intelligence, Recruitment Pipeline, Exit Interview, Nitaqat, Job Pattern Grouping | n/a | **no** — department/aggregate-level tables only |
| Payroll Budget Planner, Zakat Estimator (this session's own Phase 37 builds) | n/a | **no** — department-level or no employee data at all |

### Decision

**Switch to the real uploaded `EmployeeID` value for Gratuity, WPS, Leave Balance,
Contract Expiry, GOSI, and Succession Readiness.** This platform is used single-tenant
on the uploader's own local data — the user already knows their own employees from
every other visible column (department, salary, tenure); the hash doesn't protect
anyone in this context, it only prevents the user from cross-referencing the row
against their own spreadsheet, which is exactly the confusion reported.

**Exception, kept hash-only: `EmployeeRiskDashboard.tsx`.** This is the one module
with a genuine, concrete reason per the brief's own stated test (could plausibly be
exported/shared in a way that leaks the real ID inappropriately): it has a real
`Export CSV` download button (`EmployeeRiskDashboard.tsx:1380,1869`) that produces a
portable file that can leave the platform's local, controlled context entirely — its
privacy properties stop depending on "single-tenant local tool" the moment it's
downloaded and forwarded. None of the 6 modules being switched have any export/download
feature at all. `record_id_safe` itself is **never removed** from any module's data
model — it's still computed and returned everywhere (needed for the Phase 8/18-style
cross-link joins between engines) — this is purely an *additional* display field
(`employee_id_raw`), never a replacement, and never fabricated when no real ID column
exists (falls back to `record_id_safe` exactly as before).

**Implementation**: `_raw_id_display()` helper added to `labor_law_calculators.py`
([labor_law_calculators.py:250-259](backend/core/labor_law_calculators.py#L250-L259));
equivalent inline logic added to `contract_expiry_engine.py`, `gosi_calculator_engine.py`,
and `succession_readiness_engine.py`. Every affected candidate dataclass gained an
`employee_id_raw: Optional[str] = None` field, threaded through each `_to_dict()`
function. Two pre-existing tests (`test_gratuity_output_never_contains_raw_employee_ids`,
`test_leave_output_never_contains_raw_employee_ids`) were deliberately rewritten to
assert the **new** intended behavior (real IDs ARE now present) rather than the old one
— this is the expected consequence of a deliberate design reversal, not a regression.

### Shared search component

- `executive-ui/src/hooks/useEmployeeSearch.ts` — generic case-insensitive
  substring-match hook over any row array + a `getSearchableFields` callback.
- `executive-ui/src/components/shared/EmployeeSearchInput.tsx` — the one search-box UI
  every per-employee table renders through (matching `EmployeeRiskDashboard.tsx`'s
  existing search-input styling so it reads as the same platform pattern), with a
  result-count indicator and a clear button.

Applied to all 6 tables across 4 pages: `SaudiLaborLawCalculators.tsx` (Gratuity, WPS,
and Leave tabs — 3 separate search instances, one per tab), `ContractExpiryTracker.tsx`,
`GosiCalculator.tsx`, `SuccessionReadinessTracker.tsx`. Search matches whichever ID is
actually displayed (`employee_id_raw ?? record_id_safe`), so results always correspond
to what the user sees on screen. `EmployeeRiskDashboard.tsx` was deliberately **not**
retrofitted — it already has its own more elaborate, working multi-filter search system
(search + band/department/confidence/urgency filters across 5 memoized views); replacing
a working system with the simpler shared hook would be a regression, not an improvement,
and the brief's concern was pages with **no** search, which this page already isn't.

### Live verification (real browser, 4 pages, zero console errors)

1. **Saudi Labor Law Calculators, Gratuity tab** — uploaded the EOS reconciliation
   fixture; table shows real IDs (`EOSEMP001`...`EOSEMP005`, not hashes); typed
   "EOSEMP002" into the search box → result counter showed "1 / 5", table narrowed to
   the exact matching row. The Article 80 critical banner and new column were visible
   simultaneously, confirming Priority 1's fix live on the same page.
2. **GOSI Calculator** — uploaded the GOSI fixture; typed "GEMP002" → "1 / 5", correct
   row shown with its real ID.
3. **Contract Expiry & Renewal** — uploaded the contract-expiry fixture (10 real
   employees, `EMP001`-style IDs); typed "EMP001" → "2 / 11" (this employee has both a
   contract-expiry and an Iqama-expiry row), both rows shown, real ID displayed.
4. **Succession Readiness** — uploaded the succession fixture (60 rows); typed a
   deliberately non-matching string → "0 / 20", empty state "No employees match your
   search." rendered correctly (confirms the zero-result path, not just the happy path).

## Full regression

```
$ py -m pytest tests/ -q --ignore=tests/_smoke_test.py
1 failed, 1594 passed, 1 skipped, 65s
```

The single failure (`test_phase29_extended.py::TestCEODashboardVisualisations::
test_health_wheel_imported`) is the same pre-existing, unrelated failure noted in every
prior phase's report. **Zero unintended regressions.** 1594 passed = 1579 pre-existing +
15 new (10 Excel reconciliation + 4 GOSI re-audit + 1 GOSI `employee_id_raw` test); the
2 rewritten PII-discipline tests are counted within the 1579 baseline (same test count,
new assertions).

`npx tsc --noEmit` and `npm run build` both pass cleanly (build in 6.24s).

## Files changed

- `backend/core/labor_law_calculators.py` — `_ARTICLE_80_TOKENS`, Article 80
  classification + disclosed (never auto-applied) forfeiture amount,
  `_raw_id_display()` helper, `employee_id_raw` on all 3 candidate types.
- `backend/core/contract_expiry_engine.py`, `gosi_calculator_engine.py`,
  `succession_readiness_engine.py` — `employee_id_raw` field + population.
- `executive-ui/src/hooks/useEmployeeSearch.ts` (new)
- `executive-ui/src/components/shared/EmployeeSearchInput.tsx` (new)
- `executive-ui/src/pages/SaudiLaborLawCalculators.tsx` — Article 80 column/banner/badge,
  real-ID display + search on all 3 tabs.
- `executive-ui/src/pages/ContractExpiryTracker.tsx`, `GosiCalculator.tsx`,
  `SuccessionReadinessTracker.tsx` — real-ID display + search.
- `tests/test_eos_report_excel_reconciliation.py` (new, 10 tests)
- `tests/test_gosi_calculator_engine.py` (+5 tests: 4 re-audit scenarios, 1
  `employee_id_raw` check)
- `tests/test_labor_law_calculators.py` (2 tests rewritten for the deliberate
  PII-display reversal)
- `eos_report_reconciliation_test_data.csv` (new fixture, repo root, built from 3 of
  the workbook's real worked examples)
