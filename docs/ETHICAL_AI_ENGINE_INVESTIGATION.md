# Ethical AI Engine — Investigation Report

Date: 2026-08-06
Scope: discovery only, per instruction — no feature code written. Every claim below was verified by opening the cited file and line, or by actually executing the module against the platform's real data (not inferred from the module's docstrings or from prior report claims).

**Naming discrepancy, stated up front:** the prompt refers to `backend/core/ethical_ai_engine.py`. That exact path does not exist. The real file is **`backend/core/ethical_ai.py`** (543 lines) — confirmed via repo-wide search for every symbol named in the prompt (`EthicalAIEngine`, `audit_bias`, `govern_prediction`, `build_ethical_report`, `BiasAuditResult`, `EthicalReport`), all of which resolve to this one file. This report investigates that file. `PRODUCTION_REPORT.md:27` independently confirms the same filename and line count (542, off-by-one from a trailing blank line — immaterial).

A second naming discrepancy: `Original_Dataset_of_Employee_Attrition` (as referenced in Q4) does not exist anywhere in the repo (grepped, zero matches; no file by that name at any depth). §4 below uses the real fixtures that do exist instead: `test_employee_data.csv` (root and `executive-ui/`) and `messy_test_data.csv`.

---

## 1. Is it wired into the live request path? — **CONFIRMED DEAD** (relative to the live product)

**Every call site of the module, repo-wide** (grepped for `EthicalAIEngine`, `audit_bias`, `govern_prediction`, `build_ethical_report`, `generate_ethical_report`):

| Call site | File | Live? |
|---|---|---|
| `from backend.core.ethical_ai import EthicalAIEngine` | `frontend/app.py:85` | Streamlit only — see below |
| `"ethical_eng": EthicalAIEngine()` | `frontend/app.py:133` | Streamlit only |
| `s["ethical_eng"].audit_bias(...)` | `frontend/app.py:714` | Streamlit only |
| `s["ethical_eng"].govern_prediction(...)` | `frontend/app.py:719` | Streamlit only |
| `s["ethical_eng"].generate_ethical_report(...)` | `frontend/app.py:727` | Streamlit only |
| `from backend.core.ethical_ai import EthicalAIEngine` | `frontend/utils/session_state.py:96` | Streamlit only |
| `"ethical_eng": EthicalAIEngine()` | `frontend/utils/session_state.py:110` | Streamlit only |

**Zero references anywhere under `backend/api/`** (grepped the entire directory, not just `local_analysis_routes.py` — no matches for `ethical_ai`, `EthicalAIEngine`, or `audit_bias`). This is the same live-path-tracing method `AUDIT_REPORT.md` §1 used for every other module in this codebase.

**`frontend/app.py` is a separate, parallel Streamlit application** (`frontend/app.py:1-3`: *"Adaptive Workforce Intelligence Engine v2.1 — Streamlit Frontend. Port 8510."*), not the live product. Confirmed via three independent signals, same as `AUDIT_REPORT.md §1`'s original finding for `report_generator.py`:
1. `backend/api/main.py:56,110` mounts `create_local_analysis_router()` — this is the only router the live FastAPI app serves for analysis, and it has zero `ethical_ai` references.
2. `docker-compose.yml:38-43` — the Streamlit service is commented out entirely (*"Disabled by default. Enable only for demo/development purposes."*), unchanged since `AUDIT_REPORT.md` first documented this.
3. `executive-ui/src` (the React app the live FastAPI backend actually serves) has **zero** references to any bias/fairness/ethical term at all (see §2).

**Verdict: CONFIRMED DEAD relative to the live executive-ui + FastAPI product. CONFIRMED LIVE, but only inside the separate, non-default-enabled Streamlit app** — the exact same "PARTIALLY WIRED — live, but in the other app" pattern `AUDIT_REPORT.md §3` already documented for `report_generator.py`.

**The module-level convenience function `build_ethical_report()` (the one with the hardcoded `raw_confidence=0.75, n_samples=200, data_quality_score=0.80, auc_score=0.75` defaults named in the prompt) is called from precisely nowhere in the entire repository** — grepped, the only match is its own `def` line (`ethical_ai.py:514`). Even within the Streamlit app, it is bypassed entirely in favor of calling `EthicalAIEngine().audit_bias()` / `.govern_prediction()` / `.generate_ethical_report()` directly (see §5 for what values those direct calls actually use).

---

## 2. If wired in, is the output actually surfaced? — **N/A for the live product; CONFIRMED LIVE within Streamlit**

Since §1 established the module is not reachable from the live React/FastAPI product at all, there is no live-product answer to "is it surfaced or discarded" — it simply never runs there.

**Within the separate Streamlit app, however, it genuinely is rendered to the user**, not just computed and logged (i.e., it does *not* repeat the silent-computation failure pattern `AUDIT_REPORT.md` found elsewhere):
- Stored in session state: `frontend/app.py:914` (`"ethical_report": ethical_rep`)
- Read back and rendered: `frontend/app.py:2638-2808` — `ethical_rep.overall_ethical_status`, `.ethical_clearance_text`, `.bias_audit`, `.blocking_issues`, `.advisory_warnings` are all displayed in a dedicated Streamlit section.

**`executive-ui/src` (the live React app) — searched for every relevant symbol** (`EthicalAIEngine`, `audit_bias`, `govern_prediction`, `BiasAuditResult`, `EthicalReport`, `bias_audit`, `fairness_metric`, `protected_attribute`, `ethical_clearance`, `blocking_issues`): **zero matches anywhere.** No TypeScript interface, no React component, nothing. This is not "computed and discarded on the backend" (the AUDIT_REPORT.md pattern the prompt asked me to check for) — it's one level further back: the backend call itself never happens on the live path, so there is nothing to discard.

**Verdict: CONFIRMED DEAD relative to `executive-ui`. CONFIRMED LIVE (rendered, not discarded) within the separate Streamlit app.**

---

## 3. If not wired in, was it superseded by something else? — **No live replacement exists**

Searched `enterprise_language_guard.py` and `saudi_data_governance.py` directly for fairness/bias/protected-attribute content (`protected_attribute`, `bias_audit`, `fairness`, `disparity_ratio`, `statistical_parity`, `gender`, `nationality`): **zero matches in either file.** Neither module has any fairness logic at all — they govern different things (language/tone rules and data-residency/PDPL rules respectively).

Broader search across `backend/core/` for bias/fairness-shaped code turned up two **adjacent but non-overlapping** modules, both worth knowing about even though neither replaces `ethical_ai.py`:

- **`semantic_column_mapper.py:218`** — has its own, independent protected-attribute *detection* (`SemanticRole.PROTECTED_ATTR`, populated into `protected_attrs` and returned as part of its schema-mapping result, `:278`). This is column-role classification only — it does **not** compute fairness metrics, disparity ratios, or bias risk levels; it just flags which columns look like protected attributes as one part of a much larger semantic-mapping report. It is consumed by `backend/core/fail_safe_guardrails.py:529-530`, which only emits a generic advisory string ("Protected attributes detected... Run fairness audit") — it does not itself run one. **This detector is also not live**: `backend/api/main.py:42,66,147` imports and calls the sibling module `semantic_mapper.py`'s `SemanticMapper` only inside the inline `/api/v1/upload` endpoint, which `AUDIT_REPORT.md §1` already established the live `executive-ui` frontend never calls. `local_analysis_routes.py` has zero references to either `semantic_mapper.py` or `semantic_column_mapper.py` (grepped).
- **`confidence_governance.py`** (`ConfidenceGovernor`, `UnifiedConfidenceReport`) — overlaps in *name and general purpose* with `ethical_ai.py`'s `ConfidenceGovernance`/`govern_prediction` (confidence-band governance), but has no bias/protected-attribute audit logic of its own. Referenced only by `frontend/app.py:68` and `frontend/components/governance_panel.py:19` — same Streamlit-only, not-live status as `ethical_ai.py` itself (zero references anywhere under `backend/api/`).

**Verdict: `ethical_ai.py` has not been superseded by anything that is actually live.** Building a second fairness module would create genuine, unnecessary duplication of `ethical_ai.py`'s bias-audit logic specifically — that logic has exactly one implementation in this codebase. The two adjacent modules above solve different or narrower problems (schema-level attribute *flagging* without metrics, and *non-fairness* confidence governance) and are equally unwired.

---

## 4. Does the module's logic make sense against this platform's real data? — **Yes, there is real data to analyze — but see the bug in §5**

`Original_Dataset_of_Employee_Attrition` does not exist (see naming note above). Checked the real fixtures that do exist:

| File | Columns | Protected attributes present? |
|---|---|---|
| `test_employee_data.csv` (200 rows, used throughout Phases 1-5's live browser testing) | `EmployeeID, Department, Age, Gender, JobRole, Attrition, MonthlyIncome, OverTime, JobSatisfaction, PerformanceRating, YearsAtCompany` | **Yes — `Age` and `Gender`, both genuinely present** |
| `messy_test_data.csv` (Phase 35.5 correction fixture) | `EmployeeID, Department, OverTime, MonthlyIncome, tenure_years, job_level, performance_rating, PercentSalaryHike` | None |
| `messy_recruitment_data.csv` (Phase 5 fixture) | `CandidateID, Stage, Department, Source, ApplicationDate, HireDate, RejectionReason, RecruitmentCost` | None |

**Ran `_detect_protected_attributes()` directly against `test_employee_data.csv` (not just read the code):**
```
Age    -> age    (detection_confidence=1.0, representation_warning=True)
Gender -> gender (detection_confidence=1.0, representation_warning=False)
```
Both detected with maximum confidence (exact keyword match, `score = len(kw)/len(col_lower) = 1.0`, well above the `0.25` threshold, `ethical_ai.py:117`).

**This contradicts the framing in the prompt** — the platform's actual primary live-testing dataset does have protected-attribute columns to analyze. This is *not* a "not applicable, same as Payroll Movements" situation; there is genuinely live-relevant work for this module to do, which raises the stakes on §5's finding rather than lowering them.

---

## 5. Bugs / design issues — **one severe bug, one methodological gap, zero test coverage**

### 5a. `govern_prediction` real-values question — answered directly with evidence

**Within the Streamlit app** (the only place any of this runs), `govern_prediction` is called with genuinely computed pipeline values, not the hardcoded example defaults:
```python
# frontend/app.py:719-726
gov = s["ethical_eng"].govern_prediction(
    prediction_type="attrition",
    raw_confidence=_auc,            # frontend/app.py:675 — ml_res.best_metric_value, or 0.65 fallback only if AUC wasn't the model's best metric
    n_samples=_n_rows,               # frontend/app.py:676 — prof.n_rows if prof else len(df) — real row count
    data_quality_score=_quality,     # frontend/app.py:674 — contract.quality_score / 100.0 — real computed quality score
    auc_score=_auc,
    protected_bias_risk=ethical_rep.overall_risk_level,  # real, just-computed bias-audit result
)
```
None of `build_ethical_report`'s hardcoded defaults (`raw_confidence=0.75`, etc.) are ever exercised anywhere, because — as established in §1 — `build_ethical_report()` itself is never called by anything. The suspicion in the prompt (that the placeholder defaults might be all that ever runs) does not hold: the defaults are simply dead code inside a dead-code function, not a silent trap in a live path.

### 5b. Severe bug: continuous numeric protected attributes are not bucketed — reproduced live, not hypothetical

**`_detect_protected_attributes()` and `_compute_selection_rate()` treat every detected protected column as categorical**, grouping on raw unique values via `df.groupby(group_col)` (`ethical_ai.py:162`). Nothing in the detection or metric-computation path checks whether a column is actually continuous (like `Age`) versus genuinely categorical (like `Gender`).

**Ran the full audit against the real dataset** (`engine.audit_bias(df, target_col='Attrition', positive_label='Yes')`):
```
Age    disparity_ratio=428600000.0   risk_level=CRITICAL
Gender disparity_ratio=1.1765        risk_level=HIGH
overall_risk_level: CRITICAL
audit_summary: "...Critical risks: 1, High risks: 1. Overall risk level: CRITICAL."
```
`Age` has **34 distinct values across 200 rows** (confirmed: `df['Age'].nunique() == 34`) — an average of ~5.9 rows per "group." `_compute_selection_rate()` (`ethical_ai.py:158-168`) computes a raw attrition rate per exact age value; several of these 5-10-person groups have zero attrition by chance (e.g. ages 27, 38, 39, 41, 45, 49, 50, 51, 55, 58 all show `0.0`). `_compute_disparity_ratio()` (`ethical_ai.py:138-142`) then divides the highest group rate by the lowest, floored at `1e-9` to avoid a literal `ZeroDivisionError`: `0.4286 / 1e-9 = 428,600,000.0`. This number is then labeled `"CRITICAL"` (`ethical_ai.py:147`, gap ≥ 0.20 threshold) and drives the *entire report's* `overall_risk_level` to `"critical"` (`ethical_ai.py:232-237`, worst-single-metric logic) and would populate `generate_ethical_report()`'s blocking-issue text verbatim: *"CRITICAL BIAS RISK: Statistical parity disparity exceeds 20% threshold. Predictions must not be used for personnel decisions without expert review."* (`ethical_ai.py:385-389`).

**This is a fabricated-precision problem, not a real finding** — the platform's own established discipline elsewhere (Phase 4's `SECTOR_BENCHMARK_CONFIDENCE` labeling, Phase 5's refusal to invent a Saudi-specific cost-per-hire number, the department-normalizer's refusal to auto-merge low-confidence near-duplicates) is specifically about never presenting a number with more certainty than the data supports. A "428,600,000x disparity, CRITICAL" headline is the opposite of that discipline, and would be actively misleading — or worse, reputationally damaging — if ever shown to a real user, despite being mechanically "correct" arithmetic on the numbers it was given.

The module already computes a signal that could catch this — `representation_warning` (`True` for `Age`, correctly flagging that some group is under 10% of the total, `ethical_ai.py:125`) — but `audit_bias()`'s metric-computation loop (`ethical_ai.py:206-230`) never checks `attr.representation_warning` (or the number of distinct groups) before running `_compute_selection_rate`/`_compute_disparity_ratio` on it. The guard exists; it just isn't consulted.

### 5c. No statistical significance testing anywhere in the module

Even the `Gender` result (a real, correctly-computed 1.18x disparity, 20.0% vs 17.0% attrition, n=100 per group) is labeled `"HIGH"` risk with the same confident language as a large, robust finding would get. A 3-percentage-point gap on n=100 groups is well within normal binomial sampling noise and would not, on its own, survive a significance test (e.g., a two-proportion z-test or chi-square test) at conventional thresholds — the module has no such test anywhere in the file (grepped for `scipy`, `chi2`, `p_value`, `confidence_interval`: no matches). This is a design gap rather than an outright bug: the risk-level thresholds (`_RISK_LEVEL_THRESHOLDS`, `ethical_ai.py:28-33`) are fixed percentage-point/ratio cutoffs with no sample-size awareness at all, so identical disparity numbers get identical alarm language whether they come from a 10,000-row group or a 5-row one.

### 5d. Zero test coverage

`tests/` has no file referencing `ethical_ai` at all (grepped `tests/` for `ethical_ai`: zero matches) — unlike every module built or corrected in this session, which each shipped with a dedicated pytest file exercising real computed-value assertions. The 428-million-x bug in §5b would have been caught immediately by a test resembling this session's other modules' "hand-computed expected value" pattern; none exists.

---

## Recommendation

**(b) — needs a bug fix before this is safe to wire up and expose, but it is worth prioritizing, not deprioritizing.**

Reasoning:
- Not (c): the "no protected attributes to analyze" concern does not apply — `test_employee_data.csv`, the platform's actual primary live-testing dataset, has two genuine protected attributes (`Age`, `Gender`) that the detector finds with 100% confidence. There is real work for this module to do.
- Not (a): it is not safe to wire up and expose as-is. §5b is not a theoretical edge case — it reproduces on the very first real dataset tried, on the very first run, with default parameters. Exposing this today would put a fabricated "428,600,000x CRITICAL bias risk" figure in front of a user, on a platform whose other four-and-a-half modules (Phases 1-5) were all built around the specific discipline of never fabricating precision the data doesn't support.

**Minimum fix before exposure**, in order of necessity:
1. Bucket continuous protected attributes (at minimum `Age`) into bands (e.g. decade or quintile bins) before computing group selection rates — or, more conservatively, skip fairness-metric computation entirely for any detected attribute above a small distinct-value-count threshold (e.g. >8-10 unique values) and surface that as an explicit "too granular to audit without bucketing" note rather than a silent skip or a fabricated number.
2. Either add a minimum-group-size floor before computing a disparity ratio (e.g. require both groups to have ≥10-20 members, consistent with this codebase's existing `MIN_DEPT_GROUP_SIZE`/small-sample-suppression convention already used elsewhere — `exit_interview_intelligence_engine.py`'s `MIN_RESPONSES_FOR_AGGREGATE` is the same pattern), or add real significance testing so small-sample noise doesn't get "CRITICAL"-grade language.
3. Add a dedicated `tests/test_ethical_ai.py` with real computed-value assertions against a known fixture (including a regression test reproducing the age-bucketing case above) before any live wiring — this repo's own established practice for every other module this session touched.
4. Only after 1-3: wire `audit_bias`/`govern_prediction` into `local_analysis_routes.py` (most natural fit: alongside the existing `EmployeeRiskScorer` call in the risk-scoring endpoints, since bias auditing needs the same department_summary-adjacent context and would report against the same `Attrition`/`flight_risk` target column those endpoints already use), add the corresponding TypeScript interface + a rendered section in `executive-ui`, and follow the same live-browser-screenshot verification standard as Phases 1-5.

Not recommending immediate implementation — awaiting confirmation per instruction.
