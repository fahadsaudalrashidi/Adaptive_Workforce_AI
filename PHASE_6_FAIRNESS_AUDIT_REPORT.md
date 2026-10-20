# Phase 6 Report — Fairness / Bias Audit Engine: Fix & Live Wiring

Date: 2026-08-06
Scope: fixed the severe bug confirmed in `ETHICAL_AI_ENGINE_INVESTIGATION.md` §5b (a fabricated 428,600,000x "CRITICAL" disparity ratio, reproduced live against the platform's real `test_employee_data.csv`), added test coverage, and wired the module into the live product for the first time — it was previously reachable only from a separate, non-default Streamlit app.

**Verification method:** direct code inspection (file:line citations), test-first discipline (17 new tests, 9 of which were confirmed failing against a simulated pre-fix version of the code before the fix, all 17 passing after), a full regression run before and after, and a live Playwright browser session against the actual running backend + Vite dev server for both required scenarios, screenshots taken, console errors checked.

---

## 1. Bucketing strategy — file:line evidence

**Root cause** (`ETHICAL_AI_ENGINE_INVESTIGATION.md` §5b, re-confirmed here): `_compute_selection_rate()` (pre-fix) grouped every detected protected attribute by raw unique value via `df.groupby(group_col)`. `Age` in `test_employee_data.csv` has **34 distinct values across 200 rows** — an average of ~5.9 rows per "group." Several of these tiny groups had zero attrition by chance, and `_compute_disparity_ratio()`'s `1e-9` zero-division floor turned `0.4286 / ~0` into `428,600,000.0`, labeled `"CRITICAL"`.

**Fix — two independent, always-consulted guards**, both in `backend/core/ethical_ai.py`:

1. **Granularity gating** — `_bucket_or_skip_for_disparity()` (`:264-329`):
   - **Threshold chosen:** `_MAX_DISTINCT_VALUES_FOR_RAW_GROUPING = 8` (`:75`). Generous enough to still directly compare genuinely categorical attributes with a handful of options (e.g. up to 8 nationality categories), while catching anything more granular — the bug fixture (`Age`, 34 values) sits far above this.
   - **Bucketing method chosen: `pandas.qcut` (quantile bands), not fixed decade bins** — `_N_QUANTILE_BUCKETS = 5` (`:83`). Chosen specifically because it guarantees balanced group sizes *by construction*, regardless of the real distribution's shape — a fixed decade-of-age bin could still leave a narrow or skewed real age distribution with a handful of members in one band, reproducing the exact bug this fix closes. Non-numeric high-cardinality attributes (verified via `pd.to_numeric` coercion, `:293-294`) are **skipped entirely** with an explicit governance note (`:314-318`) rather than guessed at.
   - **`representation_warning` (already computed at detection time, previously never consulted) is now wired in** — but deliberately *not* as a third reason to skip a low-cardinality attribute outright (a real design decision made after live-testing: an early version skipped a whole 3-category `Gender` column just because one category was small, discarding a valid Male-vs-Female comparison unnecessarily). Instead, `representation_warning` is consulted downstream, at the group-exclusion stage (§2) — exactly where a single small group should be excluded without discarding the rest of a valid comparison.

2. **`audit_bias()`** (`:363-453`) now calls `_bucket_or_skip_for_disparity()` before any rate computation (`:379-385`) and discloses every bucketing/skip decision via the new `BiasAuditResult.granularity_notes` field (`:140`).

**Live-verified result** (real `Age` column, `test_employee_data.csv`): bucketed into 5 quantile bands, disparity ratio **1.38x** (was 428,600,000x) — a plausible, bounded number.

---

## 2. Minimum-group-size threshold — file:line evidence

**Threshold chosen: `_MIN_GROUP_SIZE_FOR_DISPARITY = 20`** (`:93`), deliberately **stricter** than `config.settings.MIN_DEPT_GROUP_SIZE` (5, used elsewhere for department-row "small sample" display warnings). Justification documented inline (`:85-92`): `MIN_DEPT_GROUP_SIZE` flags a department *row* as small for display purposes, but a *disparity ratio divides two rates*, amplifying small-sample noise multiplicatively rather than merely being imprecise — at n=5, a single chance-zero event reproduces exactly this bug. At n=20 with a typical ~15-20% HR attrition base rate, the chance a truly-representative group shows zero positive events by chance drops to ≈1.2% (vs ≈44% at n=5).

**Enforcement:** `_compute_selection_rate()` (`:229-262`) now takes a `min_group_size` parameter and excludes any group below it, returning the excluded group labels alongside the rates (never silently included, never silently dropped) — disclosed via `granularity_notes` (`:395-399`) and the new `FairnessMetric.n_groups_excluded_small_sample` field (`:121`).

**Bonus: two-proportion significance test implemented** (per instruction, "if straightforward"). `_two_proportion_z_test()` (`:331-350`) computes a p-value between the highest- and lowest-rate surviving groups behind each disparity ratio, using `scipy.stats.norm` (already a dependency elsewhere in this codebase — `timeseries_engine.py` — imported with the same guarded-optional-import pattern used throughout, `:41-45`). New `FairnessMetric.p_value` / `.statistically_significant` fields (`:122-123`).

**Deliberate design choice, discovered and refined via live testing:** the significance test does **not** override the existing ratio-based `risk_level`/`overall_risk_level` classification (module docstring, `:26-30`) — but after live-testing revealed this alone still produced a technically-true-but-misleading *"CRITICAL BIAS RISK... must not be used"* blocking message for `Age`'s 1.38x ratio despite it not being statistically significant (p=0.519), `generate_ethical_report()` was extended (`:607-624`) to append an explicit non-significance caveat to the blocking/advisory TEXT itself whenever none of the metrics driving that risk level reached significance — so the language a user actually reads is never unqualified. Verified live (§4 below): the blocking issue now reads *"...NOT reach conventional statistical significance (p<0.05)... treat as a signal to monitor, not a confirmed finding."*

---

## 3. Test suite — `tests/test_ethical_ai.py` (17 tests)

| Test | Asserts |
|---|---|
| `test_age_has_high_cardinality_confirming_the_bug_precondition` | Sanity precondition: `Age` genuinely has 34 distinct values (> threshold) |
| `test_age_disparity_no_longer_fabricated` | `was_bucketed=True`; disparity `< 20.0` (sanity bound) and `≈1.3815` (exact observed value) |
| `test_age_disparity_matches_independent_hand_computation` | Independently rebuilds bucketed rates via `pandas.qcut` directly (not calling the engine's own function) — exact match |
| `test_age_bucketing_note_discloses_what_happened` | Bucketing is disclosed in `granularity_notes`, never silent |
| `test_overall_risk_level_no_longer_forced_critical_by_fabricated_age_ratio` | Re-asserts the bound driving `overall_risk_level` |
| `test_min_group_size_exclusion` | A 3-person `"Other"` subgroup is excluded (not in `group_rates`), `Male`/`Female` (n=100 each) still compared correctly; exclusion disclosed |
| `test_below_floor_group_never_silently_included` | Off-by-one boundary: exactly `floor-1` members excluded → fewer than 2 comparable groups → no metric computed, disclosed |
| `test_high_cardinality_non_numeric_attribute_is_skipped_not_guessed` | 15-category non-numeric attribute is skipped with an explicit note, never bucketed or guessed |
| `test_genuinely_fair_data_yields_low_risk` | **True-negative**: near-equal rates (15% vs 16%, n=200 each) → `risk_level` in `{acceptable,low,medium}`, `statistically_significant=False` |
| `test_genuinely_disparate_data_is_correctly_flagged` | **True-positive**: real 25% vs 5% disparity (n=200 each) → `disparity_ratio==5.0` exactly, `risk_level=="critical"`, `statistically_significant=True`, `p_value<0.001` — confirms the fix didn't neuter the module |
| `test_no_protected_attributes_detected_is_honest_not_fabricated` | No protected attributes → empty results, honest summary |
| `test_detect_attrition_target_column_finds_real_column` / `_none_when_absent` | New target-detection helper (§4) works against real and messy fixtures |
| `test_generate_ethical_report_caveats_non_significant_critical_result` | The blocking-issue TEXT for `Age` contains the non-significance caveat |
| `test_generate_ethical_report_no_caveat_when_genuinely_significant` | The true-positive case does **not** carry the caveat (it's specifically for non-significant results) |
| `test_bias_audit_to_dict_is_json_safe_and_complete` / `test_ethical_report_to_dict_is_json_safe` | New serializers (§4) are JSON-safe and complete |

**Test-first verification, exactly as requested ("git stash or otherwise verify"):** since this repo has no `.git` (confirmed: `git status` → "not a git repository"), the fixed `ethical_ai.py` was backed up, then temporarily patched in place to simulate the pre-fix behavior (raw column grouping, `min_group_size=0`, bucketing disabled) via a scripted string-replace — not a manual edit, to keep the change mechanical and reversible. Running the suite against that simulation: **9 of 13 then-existing tests failed** (`StopIteration`/`AssertionError`, confirming the tests are genuinely coupled to the fix, not vacuous). The real fixed file was then restored from the backup and the syntax/import re-verified before continuing — **all 13 (later 17) tests pass**.

---

## 4. Live route + live frontend page

**New live route confirmed mounted:**
```
POST /api/local/fairness-audit
```
(`backend/api/local_analysis_routes.py:1648`; confirmed via direct route-table inspection, same method as every prior phase report.)

**Pipeline** (mirrors the established Overtime/Payroll/Recruitment pattern exactly): Saudi HR column normalization → governance scan (dedup + PII/leakage, same as every other module) → `detect_attrition_target_column()` (new helper, `ethical_ai.py:913-934`, mirrors `EmployeeRiskScorer`'s private `_detect_target_column` candidate list — `flight_risk`/`attrition`/`Attrition`/`turnover`/`label`/`target`/`resigned`/`left_company` — for consistency, kept as an explicit local list since the original is a private method) → `audit_bias()` → (only if a target column was found) `EmployeeRiskScorer.score_dataframe()` for **real** AUC/sample-size/quality context → `govern_prediction()` → `generate_ethical_report()`.

**Real values, not placeholder defaults — the original investigation's central concern, closed with evidence:** the route (`local_analysis_routes.py:1745-1784`) deliberately never calls `build_ethical_report()` (the convenience function with hardcoded `raw_confidence=0.75` etc. defaults, confirmed in the investigation to be called nowhere in the entire repo). Instead it feeds `govern_prediction()` genuinely computed values — `auc` from `EmployeeRiskScorer`'s real `model_metrics['roc_auc']` (fallback `0.65` only when unavailable, mirroring the Streamlit app's own documented fallback, `frontend/app.py:675`), `n_samples` from the real scored-record count, `data_quality_score` from the real governance scan's `missing_value_pct`. **Live-verified**: `test_employee_data.csv` produced `raw_confidence=0.5391` — a real, model-derived AUC, not 0.75.

**Bug found and fixed during live verification (not in the original plan, discovered by testing):** the first version of this route called `govern_prediction()` unconditionally, even when no target column existed — fabricating a confidence-governance verdict for an "attrition prediction" that was never actually made. Fixed (`local_analysis_routes.py:1750-1784`): `governance_results` is now only populated when `target_col` is truthy; live-verified with `messy_test_data.csv` (no target column) — `overall_ethical_status` changed from a spurious `"Fail"` to the correct `"Pass"`, `governance: []`.

**New live frontend page confirmed:** "Fairness / Bias Audit" (`executive-ui/src/pages/FairnessAuditTracker.tsx`, 457 lines) in the sidebar's Analysis nav group, reachable via `App.tsx`'s `case 'fairness'`. Bilingual EN/AR throughout, RTL-consistent with the other five modules.

**Ethical disclaimer confirmed rendered, not dropped** (per instruction) — `FairnessAuditTracker.tsx` renders `bias_audit.ethical_disclaimer` unconditionally whenever protected attributes are present; live-verified text: *"ETHICAL DISCLAIMER: This bias audit is statistical and does not constitute a legal determination of discrimination..."*

**Honest "not applicable" state confirmed** (per instruction, matching the Payroll/Recruitment pattern) — when `protected_attributes` is empty, the page renders a dedicated panel (*"No protected attributes detected in this upload"*) listing which columns would activate the feature, never an empty error or a hidden section.

**New serializers added** (needed for JSON wiring, module had none before): `bias_audit_to_dict()` (`ethical_ai.py:807-846`), `ethical_report_to_dict()` (`:848-871`), `unavailable_bias_audit_result()` (`:874-897`).

---

## 5. Live browser verification — both required scenarios

Live Playwright session against the running backend (`python backend/api/main.py`, port 8000) + Vite dev server (port 5173).

### (a) Real bias data — `test_employee_data.csv` — `07_fairness_real_data.png`

- `test_employee_data.csv · 200 rows`
- Ethical clearance: **FAILED** — `Age` disparity **1.38x** (bucketed, 5 quantile bands) and `Gender` disparity **1.18x**, both shown with the exact bucket ranges and percentage-point gaps
- Blocking issue text includes the non-significance caveat verbatim: *"...did NOT reach conventional statistical significance (p<0.05)... treat as a signal to monitor, not a confirmed finding"*
- Fairness metrics table shows `Significant?` = **No (p=0.519)** for Age, **No (p=0.585)** for Gender — both correctly identified as plausible sampling noise, not confirmed disparities
- "Data granularity notes" box discloses the Age bucketing
- Prediction Confidence Governance section shows real `AUC 0.539`, `Unreliable (13%)` band, suppressed
- Ethical disclaimer rendered in full
- **Zero console errors**

### (b) No protected attributes — `messy_test_data.csv` — `08_fairness_not_applicable.png`

- `messy_test_data.csv · 61 rows`
- Ethical clearance: **PASSED** — *"No critical bias risks or confidence failures detected"*
- "No protected attributes detected in this upload" panel, listing the columns that would activate the feature
- **Zero console errors**

---

## 6. Full-Suite Regression Trail

| Checkpoint | Result |
|---|---|
| Before this phase (end of Phase 5) | 39 failed, 1271 passed, 1 skipped |
| After this phase | 39 failed, **1288 passed**, 1 skipped *(+17 new fairness/bias-audit tests)* |

Same 39 pre-existing, unrelated `passlib`/bcrypt failures throughout. **Net: zero regressions, +17 new tests, all passing.**

---

## Summary Table

| Requirement | Status |
|---|---|
| Bucketing strategy (numeric, high-cardinality) | ✅ `pandas.qcut`, 5 quantile bands, `ethical_ai.py:264-329` |
| Skip strategy (non-numeric, high-cardinality) | ✅ explicit note, never guessed, `ethical_ai.py:319-323` |
| `representation_warning` wired into the guard | ✅ consulted at group-exclusion stage, not attribute-skip stage (refined after live testing) |
| Minimum-group-size floor | ✅ 20, justified against `MIN_DEPT_GROUP_SIZE`, `ethical_ai.py:85-93,229-262` |
| Significance testing (bonus) | ✅ two-proportion z-test, `ethical_ai.py:331-350`, wired into report language |
| Tests (fail pre-fix, pass post-fix) | ✅ 17 tests, 9 confirmed failing pre-fix, 17/17 passing post-fix |
| Live route | ✅ `POST /api/local/fairness-audit` |
| Live frontend page | ✅ "Fairness / Bias Audit" nav item |
| Real bias data scenario | ✅ screenshot, 1.38x (not 428,600,000x), zero console errors |
| No-protected-attributes scenario | ✅ screenshot, honest "not applicable", zero console errors |
| Full regression | ✅ 1271 → 1288 passed, same 39 pre-existing unrelated failures |
