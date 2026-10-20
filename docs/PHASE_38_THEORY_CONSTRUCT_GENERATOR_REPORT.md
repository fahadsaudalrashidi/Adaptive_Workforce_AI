# Phase 38 — Theory-Grounded Construct Generator (Live-Wired)

New, live-wired module implementing the 4 theory-grounded formulas confirmed computable by the Phase 38
investigation of the real Al-Qahtani dataset (`القحطاني_تحقيق_الأعمدة_المخفية.md`), generalized across
companies, plus honest per-dataset degradation for the 3 formulas confirmed unavailable on that dataset.
Reachable today at **Theory-Grounded Constructs** (sidebar → Analysis group) → `POST /api/local/theory-construct-generator`.

## 1. Whitespace/naming bug fix

- **`backend/core/categorical_value_normalizer.py`** (new, 56 lines) — a shared Tier-1 exact-normalization
  utility (`normalize_categorical_value()`, line 35), generalized from `department_normalizer.py`'s proven
  `_exact_normalize()` pattern, for any module that needs to collapse whitespace-duplicated categories
  (`'Less than 5 years'` vs `' Less than 5 years'` vs `'\xa0Less than 5 years'`).
- **Honest correction on scope**: investigating further before wiring this in broadly, the real existing
  V1 value-parsing call sites (`theory_grounded_construct_engine.py`'s `_binarize_overtime`,
  `theory_aware_column_mapper.py`'s `_validate_scale`) already apply `.str.strip().str.lower()` locally at
  each comparison site — this was **not** a reproduced live defect in already-tested code. The new utility
  is used throughout `theory_construct_generator_engine.py`'s own value parsing (`_parse_binary` at line
  276, `_parse_ordinal_or_numeric` at line 301) rather than retrofitted into other engines, to keep the
  "zero regressions in pre-existing tests" guarantee absolute. Documented in the module's own docstring.
- **WorkLifeBalance/Work_Live_Balance typo fix**: `theory_construct_generator_engine.py:139-144`
  (`_TIERS_WORKLIFEBALANCE`) adds an explicit STRONG_PROXY tier matching `work_live_balance` (the real
  dataset's typo) alongside the DIRECT `work_life_balance` tier — confirmed live on the real file
  (`Work_Live_Balance` detected, STRONG_PROXY) and unit-tested
  (`test_worklifebalance_tiered_detection`, `tests/test_theory_construct_generator_engine.py:238-246`).

## 2. The 4 built formulas, with generalized detection

All in `backend/core/theory_construct_generator_engine.py`, entry point `analyze_theory_constructs()` (line 450):

| Formula | Detection (DIRECT → STRONG_PROXY tiers) | Real Al-Qahtani result | Synthetic rich-company result |
|---|---|---|---|
| **BurnoutRisk** = OverTime × (5−WLB) | `_TIERS_OVERTIME` (129), `_TIERS_WORKLIFEBALANCE` (139) | STRONG_PROXY via `Work_Live_Balance` (typo-tolerant) | DIRECT via `WorkLifeBalance` |
| **TenureRatio** = YAC/(TWY+1) | `_TIERS_YEARS_AT_COMPANY` (167), `_TIERS_TOTAL_WORKING_YEARS` (172) | STRONG_PROXY via `Years_experience_lastorganization`/`Years_Experience` (derived, per investigation evidence, cited in the governance note shown to the user) | DIRECT via `YearsAtCompany`/`TotalWorkingYears` |
| **SatisfactionIndex** = mean(available components, ≥2 required) | tiers per component (146-158) | STRONG_PROXY, 3 of 4 components (`RelationshipSatisfaction` not detected — disclosed) | DIRECT, all 4 components |
| **EngagementScore** = JobInvolvement × JobSatisfaction | `_TIERS_JOB_INVOLVEMENT` (160-165) | STRONG_PROXY via `Job_Engagement` (disclosed substitute, not silent) | DIRECT via `JobInvolvement` |

Live-verified via Playwright against the real running app (screenshots below) — both datasets rendered
identically to the backend's own JSON, zero console/page errors.

## 3. Honest degradation — IncomePerLevel, CareerProgression, SalaryGrowth

- **JobLevel monotonicity gate** — `_validate_joblevel_monotonic()` (line 329): groups mean salary by
  numeric level and requires a non-decreasing or non-increasing sequence. Reproduces and correctly rejects
  the exact `Allowances` false-positive from the investigation
  (`test_joblevel_monotonicity_gate_rejects_allowances_pattern`, tests file line ~178) and accepts a
  genuine monotonic JobLevel (line ~187).
- **PercentSalaryHike ratio gate** — `_validate_salary_hike_ratio()` (line 354): requires values in a
  plausible percentage range **and** (a defense-in-depth fix made during this build, since the naive range
  check alone let the `Allowances` {0,1,2,3,4} pattern through) enough distinct/decimal variation to not be
  a disguised small integer count. Both the range-only gap and its fix are covered by
  `test_salary_hike_ratio_gate_rejects_allowances_style_integer_count`.
- On the real Al-Qahtani dataset: no `JobLevel`/`PercentSalaryHike`/`PerformanceRating` column exists at
  all (confirmed by the Phase 38 investigation), so all 3 degrade with the honest reason plus explicit
  "what would activate this" guidance (`analyze_theory_constructs`, unavailable-branch construction,
  lines 747, 776-793) — shown live in the UI's "Not Available" section.
- On the synthetic rich-company fixture (real JobLevel correlating monotonically with salary, real
  percentage-shaped hike values): all 3 activate at DIRECT evidence — proving this is genuinely re-checked
  per dataset, not hardcoded "always unavailable."

## 4. Live wiring

- **Backend route**: `backend/api/local_analysis_routes.py:2901` (`POST /api/local/theory-construct-generator`),
  mirroring the exact `/leave-balance-calculator` request/response pattern (governance scan →
  `analyze_theory_constructs` → `theory_construct_report_to_dict`).
- **Frontend**: `executive-ui/src/pages/TheoryConstructGenerator.tsx` (397 lines, modeled on
  `OvertimeCostIntelligence.tsx`), registered in `Sidebar.tsx:323` (Analysis group, after "Saudi Labor Law
  Calculators", `badge: 'new'`), `types/index.ts` `NavPage` union, and `App.tsx:123` route case.
- Confirmed via `npx tsc --noEmit` — clean, zero new TypeScript errors.

## 5. Tests and regression

- **`tests/test_theory_construct_generator_engine.py`** — 25 new tests, all passing:
  - Real Al-Qahtani fixture (`al_qahtani_theory_construct_test_data.csv`, a CSV export of the exact real
    1,191-row file, committed as a repo fixture): the 4/3 split, hand-computed BurnoutRisk/TenureRatio/
    EngagementScore values for row ID=11 (matching the investigation's numbers exactly:
    TenureRatio = 3.75/4.75 = 0.7895), SatisfactionIndex's 3-of-4-component disclosure, and the 3 honest
    unavailable reasons.
  - Synthetic "different company" fixture: all 7 formulas activate, **every single input evidence-strength
    is DIRECT** — the core generalization proof, not always falling back to Al-Qahtani proxies.
  - Both validation-gate rejection tests reproducing the investigation's exact `Allowances` numbers.
  - WorkLifeBalance typo-tolerant parametrized detection test.
  - Empty/no-column honest-degradation tests.
- **Full suite before/after**: 1,853 passed / 2 skipped / 10 failed (pre-existing, unrelated — 9 auth
  `httpx2`/`_IncludedRouter` framework-version gaps, 1 stale `test_health_wheel_imported` — both diagnosed
  earlier this session) → **1,878 passed / 2 skipped / 10 failed** after this phase. **Zero regressions,
  +25 new passing tests, identical pre-existing failure set.**

## 6. Live browser verification

Screenshots captured via Playwright against the real running app (`localhost:5173` → `localhost:8000`),
zero console/page errors on either upload:

- **Real Al-Qahtani data**: "4 / 7" computed constructs, all `STRONG PROXY` badges, `Work_Live_Balance`
  and `Job_Engagement` and `Years_experience_lastorganization`/`Years_Experience` shown as the actual
  detected proxy columns, "3 / 7" not-available with disclosed reasons.
- **Synthetic rich-company CSV** (clean `YearsAtCompany`/`JobLevel`/`PercentSalaryHike`/... column names,
  30 rows): "7 / 7" computed, every input badge `DIRECT`.

## Files changed/added

- `backend/core/categorical_value_normalizer.py` (new)
- `backend/core/theory_construct_generator_engine.py` (new, 848 lines)
- `backend/api/local_analysis_routes.py` (+2 import lines, +1 route)
- `executive-ui/src/pages/TheoryConstructGenerator.tsx` (new, 397 lines)
- `executive-ui/src/layout/Sidebar.tsx`, `src/types/index.ts`, `src/App.tsx` (nav wiring)
- `tests/test_theory_construct_generator_engine.py` (new, 279 lines, 25 tests)
- `al_qahtani_theory_construct_test_data.csv` (new fixture, repo root, real dataset CSV export)

No file in `v1_theory_grounded_pipeline_LEGACY_not_used_by_frontend/` or any other previously-audited
engine was modified.
