# Phase 39 — Attrition-Prediction/Theory System Removal & Enterprise Rebrand

## 1. Step 1 — Dependency graph (investigated before any deletion)

Traced every real `import` statement (not docstring/comment mentions — those were checked separately
and are harmless prose) into the systems slated for removal.

### The critical fork this investigation surfaced

`employee_risk_scoring.py` (`EmployeeRiskScorer`) is **not** ML-trained prediction — it is a deterministic,
weighted-formula risk score (confirmed: no `.fit()` call anywhere in the file) — but it is the shared data
backbone for essentially the whole "Executive Command" section: **CEO Dashboard, Executive Dashboard,
Decision Center, Workforce Intelligence, Risk Segmentation, Scenario Planning, Theory Drivers, Governance
Panel, Board Reports, Intelligence Archive, Data Intake** (11 pages; `scored_result` appears 68 times in
`local_analysis_routes.py`). The CEO Dashboard's hero "Workforce Stability Index" is `100 − risk_score`
from this engine. While reading its scoring logic I also found a real defect (§2 below): a fully random
score for rows with no matched data.

**I raised this to the user before touching anything** (a decision this consequential — whether to delete
11 executive-facing pages — deserved explicit direction rather than a unilateral call). **Decision: Contained
removal** — keep `employee_risk_scoring.py` and all 11 dependent pages; fix the random-fabrication defect
as a small, separate, contained fix.

### Full dependency graph and resolution

| File removed | Real importers found | Resolution |
|---|---|---|
| `theory_construct_generator_engine.py` | `local_analysis_routes.py` (Phase 38's own route) | Import + `/theory-construct-generator` route removed |
| `theory_grounded_construct_engine.py` | `main.py` (V1 `/analyse`) | Removed with the V1 chain (below) |
| `theory_aware_column_mapper.py` | `main.py`, `enterprise_onboarding_pipeline.py`, `theory_grounded_construct_engine.py`, **`exit_interview_intelligence_engine.py`** | First 3 removed with their files. `exit_interview_intelligence_engine.py` (a real, live, kept module) only imported 3 string constants (`EVIDENCE_DIRECT`/`STRONG_PROXY`/`WEAK_PROXY`) for its own text-theme evidence labeling — **inlined locally**, zero behavior change (`exit_interview_intelligence_engine.py:69-75`) |
| `ml_validation_engine.py` | `local_analysis_routes.py` (Phase 20 optional ML report) | Import removed; `_ml_validation` kept as an always-`{}` dict — every downstream consumer (`run_workforce_simulation`, `run_executive_decision_intelligence`, `compute_executive_indices` **[WSI]**, `compute_executive_roi`) already treated it as optional via `_ml_validation if _ml_validation else None`, so all 4 degrade exactly as before with zero changes to those engines (`local_analysis_routes.py:1073-1080`) |
| `ml_router.py` | `main.py` (V1), **`automl_engine.py`** (relative import, initially missed by the absolute-path grep) | `main.py`'s V1 chain removed; `automl_engine.py` had zero live consumers of its own (dead code extending the same dead ML system) — deleted too |
| `leakage_detector.py`, `model_truth_audit.py` | only `ml_router.py` | Removed with it |
| `enterprise_onboarding_pipeline.py` | **zero live consumers**, not wired to any route | Confirmed pre-existing dead code (its "Theory Compatibility Scan" stage existed only to feed the deleted system) — deleted |
| `categorical_value_normalizer.py` | only `theory_construct_generator_engine.py` (today's own build) | Deleted — would have had zero consumers left |
| V1 chain in `main.py` (`/api/v1/upload`, `/analyse`, `/session/{sid}`, `/export/{sid}/csv`, `DatasetProfiler`, `SemanticMapper`, `AdaptiveRouter`, `DataHealer`, `FeatureFactory`, `ModelInputContract`, `TemporalValidationGuard`, `RiskIntelligence`, `InsightGenerator`, `BiosignalAdapter`) | Confirmed **zero** frontend callers all session (`executive-ui` never calls any `/api/v1/*` route) | Entire chain removed; `main.py` cut from 417 to 118 lines, keeping only auth mounting, `/api/local/*` mounting, and `/api/v1/status` |

**No dependent was silently broken** — every real consumer found was either removed with its parent system or given a precise, minimal fix.

## 2. Real bug found and fixed: risk-score fabrication (per the "Contained removal" decision)

`employee_risk_scoring.py:_score_row` previously did, for any employee row with zero usable construct
values: `raw_score = 25.0 + rng.uniform(-5.0, 15.0)` — a number with **no connection to any real data in
that row**, inconsistent with every other module's "honest unavailable, never a guessed figure" discipline
established throughout this session. Every row (even ones with real signal) also got an unconditional
`±3pt` random jitter, and `stability` got its own `±2pt` jitter on top.

**Fix** (`employee_risk_scoring.py`, `_score_row` and `score_dataframe`): the zero-signal case now returns
a fixed, non-random `25.0` (the existing `confidence="low"` flag already discloses that this figure has
no real signal behind it); both jitter terms were removed since a score computed from real per-row inputs
should not have injected noise on top. The now-fully-unused `rng` parameter/generator was removed from the
call chain. This is a real, if narrow, fix — not a rewrite of the scoring formula itself (risk-band
thresholds, construct weights, and every other module reading `risk_score_0_100` are untouched).

## 3. Complete removal — files deleted

**Backend (10 files):** `theory_construct_generator_engine.py`, `theory_grounded_construct_engine.py`,
`theory_aware_column_mapper.py`, `ml_validation_engine.py`, `ml_router.py`, `leakage_detector.py`,
`model_truth_audit.py`, `enterprise_onboarding_pipeline.py`, `categorical_value_normalizer.py`,
`automl_engine.py`.

**Frontend (1 file):** `executive-ui/src/pages/TheoryConstructGenerator.tsx` (today's Phase 38 page) —
plus its `App.tsx` import/case, `Sidebar.tsx` nav entry + now-unused `FlaskConical` icon import, and the
`'theoryconstructs'` `NavPage` union member.

**`main.py`** rewritten from 417 → 118 lines (V1 chain removed, auth + `/api/local/*` mounting + `/status`
kept).

**`local_analysis_routes.py`**: `ml_validation_engine`/`theory_construct_generator_engine` imports and the
`/theory-construct-generator` route removed; the Phase-20 ML-validation call block replaced with a fixed
empty dict (§1 table).

**Test files removed entirely (6):** `test_theory_aware_column_mapper.py`, `test_theory_grounded_construct_engine.py`,
`test_theory_construct_generator_engine.py`, `test_phase20_real_ml_validation.py`, `test_phase20_smoke_cleanup.py`,
`test_phase4_integration.py` (Phase 4 = the theory-engine integration tests, confirmed via its own docstring).

**Test files surgically trimmed (6)**, unrelated tests kept:
- `test_exit_interview_intelligence_engine.py` — import repointed to the inlined constants
- `test_phase26_ui_polish.py` — 5 of 10 tests removed (ml_validation shape checks); 5 unrelated UI-file-existence tests kept
- `test_phase27_simulation.py` — 2 of 12 tests removed (real-ML-feature-importance path); 10 kept, including the driver-only-fallback test that already covers `ml_validation=None`
- `test_phase6_enterprise_deployment.py` — `TestEnterpriseOnboardingPipeline` (18 tests) and 2 onboarding-based tests inside `TestEnterpriseExportSafety` removed; `TestROIEstimationEngine` and the remaining export-safety tests kept (independent modules)
- `test_phase24_release_hardening.py`, `test_phase28_enterprise_transformation.py`, `test_phase29_executive_experience.py`, `test_routing_regression.py` — one broken import/assertion each removed (`test_all_core_modules_import`'s `ml_validation_engine` import line, 2x `test_ml_validation_engine_unchanged`, `test_smote_not_applied_before_split`)

**Repo fixture removed:** `al_qahtani_theory_construct_test_data.csv` (existed solely for the deleted engine).

**Confirmed no orphaned references remain** — swept `backend/` and `executive-ui/src/` for both absolute
*and* relative (`from .x import`) references to every deleted module name; the relative-import sweep is
what caught `automl_engine.py`'s `from .ml_router import ...`, missed by the first absolute-path-only grep.
The Desktop archive (`الكود_الغني_عن_التعريف/`) was left untouched — confirmed still holds all 15 originally
exported files.

## 4. Rebrand decisions

- **`config/settings.py`** (the file's own comment calls it "the single authoritative source — used by UI +
  all reports"): `PLATFORM_NAME` "Adaptive Workforce Intelligence Engine" → **"AWI Enterprise Intelligence
  Platform"**; `PLATFORM_TAGLINE` → "Enterprise Intelligence — HR Operations, Business Intelligence & AI
  Analysis"; version bumped 2.5.1 → **3.0.0** (a real architectural removal + rebrand, not a patch).
  Verified live: `GET /api/v1/status` now returns `{"platform":"AWI Enterprise Intelligence Platform","version":"3.0.0"}`.
- **`Sidebar.tsx`** top branding subtitle: "Enterprise Platform" → "Enterprise Intelligence Platform" (EN/AR).
- **`App.tsx`** default company-name fallback (shown before any dataset is uploaded): "Adaptive Workforce
  Intelligence" → "AWI Enterprise Intelligence".
- **`DataUpload.tsx`** (the landing page): removed the "Theory Engine" capability badge/readiness item in
  both places it appeared (`CapabilityBadge` grid and `ExecutiveReadinessSection`) — that capability
  genuinely no longer exists, so continuing to show it (even as "ready"/"not ready") would have been
  actively misleading, not just stale naming. "Attrition Model" relabeled to **"Workforce Risk Analysis"**
  in both spots — the underlying capability (`employee_risk_scoring.py`) is real and kept, just not a
  predictive/trained model, so the label now matches what actually runs.
  The backend `theory_activation_allowed`/`can_run_theory_engine` fields themselves were left alone
  (4 existing tests assert on that response shape) — this was a display-layer-only fix, deliberately not a
  backend schema change, per "prefer smallest possible change."
- **What was deliberately left alone:** `TopBar.tsx`'s "AWI Platform" badge (already brand-neutral, no
  edit needed) and every module-specific page name (Financial Intelligence, GOSI Calculator, etc.) — those
  already accurately describe real, kept features and needed no rebranding.

## 5. Step 4 — Business-platform proposals

**Proposed but not implemented this session** (documented for a future pass, with reasoning):

1. **Revive `PlatformWalkthrough.tsx` as a guided "Get Started" tour.** Found during this phase: a
   complete, well-built 9-step walkthrough component already exists (`executive-ui/src/pages/PlatformWalkthrough.tsx`,
   602 lines) but is **not wired into the app anywhere** (no nav entry, no `App.tsx` case) — genuinely
   orphaned, unrelated to today's removal. It would be a strong, low-effort win for a "cohesive enterprise
   product" feel. **Not implemented now** because 2 of its 9 steps ("Theory Insights", "ML Validation") are
   literally about the systems just removed — wiring it in as-is would reintroduce exactly the misleading-capability
   problem just fixed in `DataUpload.tsx`. It needs those 2 steps rewritten (e.g., replaced with "Business
   Intelligence Domains" and "AI Business Analyst" steps) before it's honest to ship — a content-authoring
   task, not a wiring task, and more scope than warranted as an add-on to an already-large removal phase.
2. **A cross-domain executive summary view** — one page pulling a single real KPI from each of the 6 BI
   domains + HR risk into one glance, rather than requiring an executive to click through 7+ separate
   pages. Real value for a platform this broad; not built now because it would need genuine design work
   (which metric per domain, layout) rather than a mechanical edit, and risks scope creep on top of an
   already-substantial phase.
3. **Consolidate "Executive Command" naming** — the group now mixes genuinely HR-risk pages (Workforce
   Intelligence, Risk Segmentation) with cross-cutting ones (CEO Brief, Decision Center, Board Reports).
   Minor; not worth a nav-taxonomy rewrite without more real user feedback on what executives click first.

**Implemented this session** (small, low-risk, directly justified by the removal itself, not speculative):
the `DataUpload.tsx` capability-badge fix (§4) — this isn't scope creep, it's a direct, necessary
consequence of the removal (an honest platform cannot keep advertising a deleted capability), so it was
built rather than just proposed.

## 6. Tests — before/after

**Before this phase:** 1,878 passed / 2 skipped / 10 failed (end of Phase 38).
**After:** **1,631 passed / 2 skipped / 10 failed** — **identical 10 pre-existing, unrelated failures**
(9 `test_phase30_1_security.py` `httpx2`/framework-version gaps + 1 stale `test_health_wheel_imported`,
both diagnosed earlier this session, neither touched here). **Zero regressions in any remaining module.**

The 247-test drop (1878 → 1631) is fully accounted for: 6 test files deleted outright (theory/ML-specific,
~90+ tests including today's own 25) plus the 18-test `TestEnterpriseOnboardingPipeline` class, 2 more
onboarding tests, 5 ml-validation-shape tests, 2 real-ML-feature-importance simulation tests, and 4
single-line import/assertion removals — every one individually identified and justified in §3, none a
blind bulk deletion.

## 7. Live browser verification

Fresh backend + frontend restart (confirmed old processes killed, new ones serving the post-removal code).
Playwright-driven, zero console/page errors throughout:

- Clicked through **all 33 remaining nav items** — zero click failures, zero console/page errors.
- Confirmed **"Theory-Grounded Constructs" nav item is gone**; confirmed **"Theory Drivers" (the kept,
  different page) is still present** — proving the removal was precise, not a blanket nav wipe.
- Confirmed the rebrand text **"Enterprise Intelligence Platform"** renders live in the sidebar.
- **CEO Brief** renders its correct empty state ("Your CEO Intelligence Brief awaits — Upload a workforce
  dataset to activate... a live Workforce Stability Index...") — this WSI framing is intentional and
  correct per the "Contained removal" decision, not a bug.
- **Intelligence Archive** (a kept page reading real `employee_risk_scoring.py` output from prior sessions)
  renders real saved-session data correctly, average risk scores intact.
- Screenshots saved to the session scratchpad: landing/Data-Intake page, Intelligence Archive, CEO Brief
  empty state.

## Files changed/added/removed — summary

**Removed:** 10 backend engine files, 1 frontend page, 6 test files (full), 1 repo CSV fixture.
**Edited:** `main.py` (rewritten, V1 chain removed), `local_analysis_routes.py`, `employee_risk_scoring.py`
(fabrication fix), `exit_interview_intelligence_engine.py` (inlined constants), `config/settings.py`
(rebrand), `App.tsx`, `Sidebar.tsx`, `types/index.ts`, `DataUpload.tsx` (rebrand + capability-badge fix),
6 test files (surgical trims).
**Untouched, confirmed:** the Desktop archive folder, all ~18 kept HR modules, all 6 BI domain engines, AI
Business Analyst, `employee_risk_scoring.py`'s actual scoring formula/weights (only the fabrication/jitter
was removed), and all 11 Executive Command pages' real functionality.
