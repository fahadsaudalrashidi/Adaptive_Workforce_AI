# Succession Planning / Internal Mobility Readiness — Investigation Report

Date: 2026-08-06
Scope: discovery only, same discipline as every prior investigation this session. No feature code written.

**Data-fixture discrepancy, stated up front (this is the third time this exact claim has appeared in a prompt this session):** `Original_Dataset_of_Employee_Attrition`, described as "the real 1,191-row research dataset used throughout this session," **does not exist anywhere in this repository** — confirmed by filename search (`find . -iname "*Original_Dataset*"`, zero results) and by a row-count search (`find . -iname "*1191*"`, zero results). This exact false premise also appeared in `ETHICAL_AI_ENGINE_INVESTIGATION.md`'s Q4, where it was already flagged and confirmed absent. The two real, repeatedly-used fixtures are `test_employee_data.csv` (200 rows) and `messy_test_data.csv` (62 rows) — both used throughout §3 below.

---

## 1. What `CareerProgression`/`TenureRatio` compute, and whether they're live

### Formulas (both in `backend/core/theory_grounded_construct_engine.py`)

| Construct | Formula | file:line | Theory anchor |
|---|---|---|---|
| `TenureRatio` | `YearsAtCompany / (TotalWorkingYears + 1)` | `:706-780` (`_try_tenure_ratio`), formula at `:739` | "COR + Mobley (condition resource; Stage 1 evaluation anchor)" (`:769`) |
| `CareerProgression` | `JobLevel / (YearsAtCompany + 1)` | `:860-930` (`_try_career_progression`), formula at `:892` | "COR + JD-R (resource gain velocity; growth resource adequacy)", citing Allen, Bryant & Vardaman (2010) (`:904,919`) |

Both use a `+1` denominator floor "specified by the paper" to prevent division-by-zero for fresh graduates/new hires (`:738,890`) — a *bounded* floor (denominator never below 1), structurally different from and safer than the `1e-9` near-zero floor that caused the confirmed 428-million-x fabricated-ratio bug in `ethical_ai.py` earlier this session (see §5).

### Live-wiring trace

`compute_constructs()` (the module's public entry point, `:1059-1064`) is imported and called in exactly one place repo-wide: **`backend/api/main.py:53,248`**, inside the `@app.post(f"{API_PREFIX}/analyse")` endpoint (`main.py:175-176`) — the same inline `/api/v1/analyse` endpoint `AUDIT_REPORT.md §1` already confirmed **`executive-ui` never calls** ("Nothing in `executive-ui/src` calls `/api/v1/upload` or `/api/v1/analyse` at all — grepped, zero matches").

Grepped `backend/api/local_analysis_routes.py` (the actually-live path) and `frontend/app.py` (the Streamlit alternate frontend) for `theory_grounded_construct_engine`/`compute_constructs`: **zero matches in both.** This is a stronger dead-verdict than `ethical_ai.py`'s (which at least had the Streamlit app as a genuine, real, non-default consumer) — `CareerProgression`/`TenureRatio` are not reachable from *any* running frontend today, live or alternate.

`employee_risk_scoring.py` (the confirmed-live risk engine) was checked directly for any overlapping tenure/level-ratio logic under a different name: zero matches for `TenureRatio`/`CareerProgression`/`tenure_ratio`/`career_progression`. `JobLevel` appears once, only as a candidate label for the "specialty" grouping column (`:107,234`) — never as a numeric ratio input.

**Verdict: CONFIRMED DEAD.** Both constructs are computed nowhere in any live or alternate running frontend, so §2 of the original question ("is either value surfaced in `executive-ui`, or computed-and-discarded") doesn't apply in the usual sense — there's no live computation to discard in the first place.

---

## 2. Does any succession/promotion-readiness logic already exist?

Searched for `succession`, `promotion_readiness`, `internal_mobility`, `high_potential`, `hipo`, `career_path`, `readiness_score`, `bench_strength` (case-insensitive) across `backend/` and `executive-ui/src`.

| Match | What it actually is | Classification |
|---|---|---|
| `enterprise_routes.py`/`enterprise_onboarding_pipeline.py`'s `readiness_score`/`deployment_readiness_score` | SaaS **tenant onboarding** progress score (0-1, how far along a customer's deployment setup is) — unrelated to employee readiness. Also, `enterprise_routes.py` is already confirmed dead (`AUDIT_REPORT.md §1`). | (c) unrelated homonym, dead anyway |
| `hr_recommendation_engine.py`'s `"career_pathing"` category (`:24,43`) | A **reactive risk-mitigation** recommendation bucket, triggered when "Promotion Justice" (a Likert survey construct measuring perceived promotion-fairness) is detected as a top risk driver for an *already at-risk* employee. Outputs a templated action ("review this employee's career path") — never ranks, scores, or identifies high-potential employees. Confirmed **CONFIRMED LIVE** via `employee_risk_scoring.py:29-30,775` → `local_analysis_routes.py`. | (c) adjacent but not overlapping — reactive dissatisfaction-mitigation, not proactive readiness identification |
| `theory_aware_column_mapper.py`'s `PromotionFairness` construct (`:646-673`) | A Likert-5 **survey-perception** input ("do employees feel promotions are fair here") for Adams Equity Theory risk scoring — its own governance note explicitly states: *"NOT equivalent to YearsSinceLastPromotion (structural event vs. perception)"* (`:671`). Confirmed **CONFIRMED DEAD**: `theory_aware_column_mapper.py` has zero references in `employee_risk_scoring.py` or `local_analysis_routes.py` (grepped). | (b)-shaped but wrong axis (perception, not readiness) — and dead anyway |
| `hipo`/`bench_strength`/`internal_mobility`/`succession` | Zero matches anywhere in the repo, backend or frontend. | N/A |

**Conclusion: no succession-planning, promotion-readiness, or internal-mobility logic exists anywhere in this codebase, live or dead, under any name.** `hr_recommendation_engine.py`'s career-pathing bucket is the only conceptually-adjacent thing, and it solves a different problem (recommend an action for someone already flagged at-risk) than what a readiness module would (rank/identify high-potential employees proactively). Building this module would not create competing/duplicate logic — same conclusion as the Nitaqat investigation's §5 for a different feature.

---

## 3. Real data availability — split across fixtures, complete in neither

| Column needed | `TenureRatio` | `CareerProgression` | `test_employee_data.csv` (200 rows) | `messy_test_data.csv` (62 rows) |
|---|---|---|---|---|
| `JobLevel` | — | required | **absent** | present, as `job_level` (lowercase) |
| `YearsAtCompany` | required | required | present, exact name | present, as `tenure_years` (different name) |
| `TotalWorkingYears` | required | — | **absent** | **absent** |
| `PerformanceRating` | (not required by either formula, but plausible for a real readiness model) | | present | **absent** |

**No single fixture in this repo has both columns either formula needs.** `test_employee_data.csv` has `YearsAtCompany` but no `JobLevel` and no `TotalWorkingYears` at all — `TenureRatio` and `CareerProgression` would both hard-block against it (`BlockedConstruct`, `:718-729` / `:872-882`) even if the dead engine were wired live today. `messy_test_data.csv` has `job_level` and a differently-named `tenure_years`, which *could* resolve to `CareerProgression`'s inputs via fuzzy/synonym matching — but only through `TheoryAwareColumnMapper`, which is itself confirmed dead (§2), and even then it still has no `TotalWorkingYears`-equivalent at all, so `TenureRatio` cannot activate against *any* fixture in this repository as it currently exists.

**Honest classification, per instruction:** this is closer to the Recruitment Pipeline / Nitaqat "not applicable to current fixtures" situation than the Fairness Audit "real data exists" situation — but not identical to either. `PerformanceRating` (a plausible input for a *new*, custom-built readiness formula, as opposed to the two existing paper-formula constructs) does exist in `test_employee_data.csv`. If this module is built, it would need either a new synthetic fixture (the pattern already established for Recruitment Pipeline and Nitaqat) or a reformulation that doesn't require `TotalWorkingYears`/`JobLevel` specifically.

---

## 4. Nitaqat cross-link — technically feasible, but requires new plumbing, not a free join

Checked `nitaqat_compliance_engine.py`'s `NitaqatComplianceResult` dataclass (`:196-218`) directly: it is **purely aggregate** — `n_saudi`, `n_non_saudi`, `department_breakdown` (department-level, not employee-level), no per-employee identifier, no per-employee Saudi/non-Saudi list anywhere in the returned result. The per-row classification (`classified = df[nationality_col].map(_classify_saudi_status)`, computed internally during `analyze_nitaqat_compliance()`) is discarded after aggregation — never returned.

**Honest technical answer:** combining "high-readiness" + "Saudi national" per employee is **not a free join on existing outputs today** — it would require:
1. A small, real code addition to `nitaqat_compliance_engine.py` to expose per-employee Saudi-status alongside a stable row reference (not currently there).
2. Both the Nitaqat engine and a new succession/readiness engine would need to run against the **same ingested dataframe within the same request** (row-index alignment is only meaningful within one upload event, not across two independent API calls to two separate endpoints) — meaning either a new combined endpoint, or the succession module's own route calling into the Nitaqat classification helper directly.

This is a modest, well-scoped addition (not a redesign), but it is real new cross-module plumbing, not something that exists today. Feasibility: **yes, straightforward to add**; readiness: **not present now**.

---

## 5. Bugs / design issues — none of the `ethical_ai.py`-class problems apply here

Checked for the same four issue classes flagged in `ETHICAL_AI_ENGINE_INVESTIGATION.md`:

1. **Ungrounded thresholds bucketing a ratio unsafely:** Neither formula divides by a value that can approach zero in practice — the `+1` floor (`:739,892`) bounds the denominator at a minimum of 1 regardless of tenure, structurally preventing the exact "near-zero epsilon floor → fabricated multi-million ratio" bug class found and fixed in `ethical_ai.py`. No threshold/band classification logic exists downstream of either formula at all (unlike `ethical_ai.py`'s `_rate_risk()`) — these two constructs return a raw continuous value, not a risk-banded category, so there is no analogous "428,600,000x CRITICAL" failure mode possible here.
2. **The "~0.85 high / ~0.10 low" example anchors in the governance text** (`:750-751`) are descriptive, illustrative prose in the returned `governance_notes` field — not a functional threshold used anywhere in code to classify or bucket an employee. Grepped for these values elsewhere in the file and confirmed they are not referenced by any conditional logic. Worth noting as informal/uncited *language*, but it does not create a computational bug the way the Nitaqat premium constant's silent, unlabeled precision did.
3. **Hardcoded example defaults masking real values:** `compute_constructs(df, column_mappings)` (`:1059-1064`) takes no optional parameters with hardcoded defaults at all — unlike `ethical_ai.py`'s `build_ethical_report()`, there is no convenience-function trap here; the function requires real, explicitly-passed inputs every time.
4. **Zero test coverage:** Does **not** apply — `tests/test_theory_grounded_construct_engine.py` contains 61 tests, several directly exercising both constructs with hand-computed expected values (e.g. `test_tenure_ratio_plus_one_denominator_preserved`, `:751-766`, asserting `0.0 / (0.0 + 1.0) == 0.0`; blocking-behavior tests at `:544-553` confirming both constructs correctly report `BlockedConstruct` when `JobLevel`/`TotalWorkingYears` are absent).

**Conclusion: this module is unusually solid engineering — safe formula design, real theory citations, genuine hand-verified test coverage — it is simply unwired, not broken.** No bug-fixing prerequisite exists before building on top of it, unlike the Nitaqat premium constant or the `ethical_ai.py` bucketing bug earlier this session.

---

## Recommendation

**(b) — solid foundation, but two real missing pieces: live wiring and matching real data. Not a straight (a).**

The engineering foundation is the best-tested and best-designed of anything reused across this session's investigations (better than `ethical_ai.py` pre-fix, cleaner than the Nitaqat premium constant) — but:

1. **No single existing fixture has the columns either paper formula needs.** `TotalWorkingYears` doesn't exist anywhere in this repo. `JobLevel` and `YearsAtCompany` exist, but never together in one fixture, and under different casing/naming in the one place both partially appear. Building this today would mean either constructing a new synthetic fixture (as already done for Recruitment Pipeline and Nitaqat) or designing the new module around what real data actually exists (`PerformanceRating` + `YearsAtCompany`, both present in `test_employee_data.csv`) rather than strictly reusing the dead engine's exact two formulas.
2. **The entire theory-grounded construct + column-mapper subsystem is dead**, not just these two constructs — reviving `compute_constructs()` verbatim would mean either wiring a second, more elaborate construct-computation system into the live path alongside the simpler one `employee_risk_scoring.py` already uses live (a real architectural decision, not a small fix), or reimplementing just the two needed formulas directly in a new, purpose-built engine (the lighter-weight option, consistent with how every other module this session — Recruitment Pipeline, Fairness Audit, Nitaqat — built its own small, local logic rather than reviving a larger dead subsystem).
3. **The Nitaqat cross-link is real and desirable given the stated rationale, but requires a small, concrete addition** (per-employee Saudi-status exposure) that doesn't exist today — worth scoping explicitly if this module is greenlit, not assumed to be free.

If prioritized: the pragmatic path is a new, purpose-built `succession_readiness_engine.py` (matching this session's established module pattern) using `PerformanceRating` + `YearsAtCompany` (both real, present today) rather than reviving the dead `TotalWorkingYears`/`JobLevel`-dependent paper formulas verbatim, a new synthetic test fixture (same discipline as Recruitment Pipeline/Nitaqat), and — if the Nitaqat cross-link is wanted — the small per-employee-exposure addition to `nitaqat_compliance_engine.py` scoped as an explicit, separate step.

Not recommending implementation. Awaiting confirmation, per instruction.
