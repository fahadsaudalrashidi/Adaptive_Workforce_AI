# Phase 4 Modules Report — Financial Consolidation + 4 New Intelligence Modules

Date: 2026-08-06
Scope: Phase 0 (mandatory financial consolidation), Phase 0.5 (two adjacent bug fixes), Phase 1 (Overtime & Workforce Cost Intelligence), Phase 2 (Payroll Movements Tracker), Phase 3 (Exit Interview / Free-Text Intelligence), Phase 4 (sector-based benchmarking).

**Verification method for every claim below:** direct code inspection (file:line citations), a dedicated pytest file per new/changed subsystem (all real computed-value assertions, no smoke-only tests), a full regression run of the pre-existing suite before and after each phase, and — for the three new frontend pages — a live Playwright browser session against the actual running backend + Vite dev server (screenshots taken, console errors checked). Nothing below is asserted without one of these forms of verification.

---

## 1. Phase 0 — Financial Logic Consolidation (MANDATORY, done first)

### Before: four independently-calibrated financial formulas

| # | Old formula | Files (exact) |
|---|---|---|
| 1 | Flat `at_risk * 120_000` / `× 0.35` savings / `× 0.28` retained | `backend/core/executive_pdf_exporter.py:1721-1725,1761` (2 sites); `backend/core/executive_pptx_exporter.py` — **10 sites** (lines 197, 307, 413, 577, 599, 687, 798, 845, 870, 1032, 1181 pre-edit); `backend/core/executive_slide_exporter.py:287-290,586` (2 sites) |
| 2 | 9-component Cascio-Boudreau model, its own `_SECTOR_SALARY_SAR`/`_SENIORITY_SALARY_MULT`/`_COST_MATRIX`/ESG/Nitaqat constants | `backend/core/executive_roi_engine.py` (was lines 40-144) |
| 3 | Flat `SAR 9,000 × 2.0 = SAR 18,000` floor | `backend/core/workforce_simulation_engine.py:378` (pre-edit) |
| 4 | Flat `SAR 8,000/month` default | `backend/core/roi_estimation_engine.py:39` (pre-edit) |

### After: one canonical module

**Created: `backend/core/financial_intelligence_engine.py`** (new file, ~460 lines before Phase 4 additions, ~560 after). Exposes exactly the two functions the brief named, plus supporting primitives:
- `estimate_departure_cost(seniority, sector, monthly_salary_sar=None)` → `DepartureCostEstimate`
- `estimate_workforce_financial_exposure(n_at_risk, sector, seniority, monthly_salary_sar=None, retention_rate=0.28, savings_rate=0.35)` → `WorkforceExposureEstimate`
- `estimate_monthly_salary()`, `compute_departure_cost_components()`, `build_retention_roi_scenarios()`, `infer_sector_from_departments()`, `infer_seniority_from_signals()`
- All 9 Cascio-Boudreau cost-matrix constants, moved (not copied) from `executive_roi_engine.py`, with their original citations preserved verbatim: Cascio & Boudreau (2011), CIPD Middle East HR Benchmark 2023, SHRM (2022), Saudi Labour Law Art. 84, Hom et al. (2017), Gulf HR Consortium (2024).

**Every one of the 4 old call sites now imports from and calls this module — verified, not just refactored on faith:**

| File | What changed | Evidence |
|---|---|---|
| `executive_pdf_exporter.py` | 2 sites → `estimate_workforce_financial_exposure(at_risk)` | import added line ~29; both sites replaced |
| `executive_pptx_exporter.py` | 10 sites → same function | import added line ~40; all 10 replaced (verified via `grep -c "120_000"` after edit → 0 live occurrences, 1 comment) |
| `executive_slide_exporter.py` | 2 sites → same function | import added; both replaced |
| `workforce_simulation_engine.py` | `_COST_PER_DEPARTURE_DEFAULT_SAR = 9_000.0 * 2.0` → `estimate_departure_cost(_seniority, _sector)` with sector/seniority inferred from `department_summary` | line ~375-390 |
| `roi_estimation_engine.py` | `_DEFAULT_MONTHLY_SALARY_SAR = 8000.0` → `_canonical_estimate_monthly_salary("diversified", "mid")` (evaluates to 16,150.0) | line ~39-55; this module is confirmed test-only/dead in the live path (only referenced by `tests/test_phase6_enterprise_deployment.py`) so the change is for consistency, not live-path impact |
| `executive_roi_engine.py` | Its own constants/helpers (`_determine_sector`, `_determine_seniority`, `_compute_component`, `_build_roi_scenarios`) deleted; now imports and calls the canonical versions, keeping only its own report-shaped dataclasses and orchestration | lines 1-30 (imports), `_adapt_cost_components`/`_adapt_roi_scenarios` added as thin shape-adapters |

**Regression math (self-consistency check):** for a "mid/diversified" employee, the canonical 9-component model computes SAR 62,177 (low) / 121,933 (high) / **92,055 (mid, the new headline figure)** — close to the old flat SAR 120,000 figure, so existing report layouts didn't need rescaling.

**Tests added:** `tests/test_financial_intelligence_engine.py` — **40 tests**, including 6 explicit regression guards (`test_call_site_imports_from_canonical_financial_module` parametrized over all 6 files, `test_no_hardcoded_120000_formula_remains_in_exporters`, `test_no_hardcoded_18000_floor_remains_in_simulation_engine`) that inspect the actual source of each call site at test time — these fail immediately if anyone reintroduces a local formula. **Result: 40/40 passed.**

**No fifth formula was found during this work** — the only other numeric collision was `TenantTier.STARTER = "starter"  # SAR 120,000/year` in `tenant_manager.py:35`, a SaaS subscription-tier price, unrelated to attrition cost — correctly left untouched.

---

## 2. Phase 0.5 — Two Adjacent Bug Fixes

### 2a. Divergent SQLite paths (`tenant_manager.py`, `historical_intelligence_engine.py`)

**Before:** `TenantManager.__init__(self, db_path: str = "awi_tenants.db")` and `HistoricalIntelligenceEngine.__init__(self, db_path: str = "awi_history.db")` — bare relative filenames, resolved against the process's CWD. **Confirmed on disk before the fix:** `awi_tenants.db` existed in both the repo root and `backend/` (both empty, 0 rows). `awi_history.db` existed in both locations with **different row counts** (7 at root, 8 under `backend/`) — live proof the two copies had diverged, not just duplicated.

**After:** both classes default to `Path(__file__).resolve().parent.parent.parent / "data" / "<name>.db"` — the same repo-root-anchored pattern already used by `local_auth.py`. Verified: `TenantManager()` and `HistoricalIntelligenceEngine()` instantiated fresh now both resolve to `C:\Users\PvP-Pc\Desktop\Adaptive_Workforce_AI\data\awi_tenants.db` / `...\data\awi_history.db` regardless of CWD. **Data preserved, not discarded:** the more complete history copy (`backend/awi_history.db`, 8 rows) was copied to the new canonical `data/awi_history.db` path before the fix took effect, so no historical snapshot data was lost. The old root-level and `backend/`-level copies were left in place, untouched, for the user to clean up manually if desired.

**Bonus fix found while testing this area:** `local_analysis_routes.py:127` called `provision_default_tenant(_tenant_manager)` **positionally**, but the function signature is `provision_default_tenant(org_name="AWI Enterprise", tenant_id="awi-default-org", manager=None)` — so the `TenantManager` instance was silently being passed as `org_name`, causing a swallowed `Error binding parameter 2: type 'TenantManager' is not supported` on every app startup (caught only by a non-fatal `try/except` warning log). Fixed to `provision_default_tenant(manager=_tenant_manager)`. Verified: router-factory instantiation now produces zero warnings (previously logged one every time).

**Tests:** `tests/test_phase30_enterprise_productization.py` (pre-existing, 80 tests) re-run — all still pass.

### 2b. Dormant `auth_session.py` schema sharing a DB file with the live auth system

**Investigation finding:** `auth_session.py`'s `AWIRole` enum and `PERMISSION_MATRIX` dict ARE genuinely live — imported by `backend/core/local_auth.py:60` and `backend/core/security_middleware.py:16` (both part of the real, mounted `/api/auth/*` system). But the file also shipped a second, **dormant** subsystem: `AWIUser`/`AWISession` dataclasses, a 3-table SQLite schema (`awi_users`/`awi_sessions`/`awi_auth_audit`) sharing `data/awi_auth.db` with the real `local_auth.py` system, and an `AuthSessionManager` class whose `create_local_session()` took **no password at all** — it was a Phase 30D placeholder scaffold, explicitly labeled as such in its own docstring, superseded by the real, credentialed `LocalAuthManager` in `local_auth.py`. Confirmed via full-repo grep: `AuthSessionManager`/`ensure_local_admin_user`/etc. were imported only by test files, never by any live application code, and its 3 tables had never actually been created on disk in this deployment.

**Action taken:** removed the dormant subsystem entirely from `auth_session.py`, keeping only `AWIRole`/`PERMISSION_MATRIX` (the genuinely live parts). Rewrote the file's docstring to explain the removal and why. Updated `tests/test_phase30_enterprise_productization.py`'s `TestAuthSessionFoundation` class to drop the 8 tests that exercised the deleted, credential-less session manager, keeping the 5 tests that exercise the real role/permission taxonomy, and added a new regression guard (`test_dormant_session_manager_no_longer_exists`) asserting the removed names never silently reappear.

**Verified:** `local_auth.py`, `security_middleware.py`, `auth_routes.py` all still import cleanly. Full auth-related test run: same 39 pre-existing failures (see below — a pre-existing environment issue, not caused by this change), zero new failures.

---

## 3. Full-Suite Regression Trail (every phase, cumulative)

| Checkpoint | Result |
|---|---|
| Before any Phase 0-4 work (documented in this session's earlier `AUDIT_REPORT.md`) | 39 failed, 1113 passed, 1 skipped |
| After Phase 0 (financial consolidation) | 39 failed, 1146 passed, 1 skipped *(+40 new financial tests, −8 removed dormant-auth tests, +1 new guard test = +33, checks out exactly)* |
| After Phase 0.5 (path fix + auth_session trim) | same, confirmed no change in pass/fail composition beyond the above |
| After Phase 1 (Overtime engine) | 39 failed, 1161 passed *(+15)* |
| After Phase 2 (Payroll tracker) | 39 failed, 1176 passed *(+15)* |
| After Phase 3 (Exit interview engine) | 39 failed, 1194 passed *(+18)* |
| After Phase 4 (Sector benchmarking) | 39 failed, 1211 passed *(+17)* |

**The 39 failures are the same pre-existing environment issue in every single run** — `passlib.exc.MissingBackendError: bcrypt: no backends available` and a `TestClient(app=app)` signature mismatch in `tests/test_phase30_1_security.py`, both already documented in this session's prior `AUDIT_REPORT.md` §4, confirmed unrelated to any of this work (reproduced with a full traceback showing the failure originates inside `passlib`/`starlette` library code, not this codebase). **Net: zero regressions introduced across all 6 phases, +98 new tests, all passing.**

---

## 4. Phase 1 — Overtime & Workforce Cost Intelligence

**Files created:**
- `backend/core/overtime_cost_intelligence_engine.py` (new, ~330 lines) — `analyze_overtime_cost_intelligence(df, department_summary, risk_elevated_threshold=55.0)`.
- `tests/test_overtime_cost_intelligence_engine.py` (new, 15 tests, **all passing**).
- `executive-ui/src/pages/OvertimeCostIntelligence.tsx` (new page).

**Files modified:** `backend/api/local_analysis_routes.py` (+1 import block, +1 endpoint, ~110 lines), `executive-ui/src/types/index.ts` (+`'overtime'` to `NavPage`), `executive-ui/src/layout/Sidebar.tsx` (+nav item), `executive-ui/src/App.tsx` (+import, +switch case).

**Live route:** `POST /api/local/overtime-cost-intelligence` — confirmed mounted (`create_local_analysis_router()` route list inspected directly, path present). Reuses the existing governance-scan pipeline (`SecureFileIngestion`) and `EmployeeRiskScorer` (for department risk cross-reference) already live in this same router.

**Live frontend page:** "Overtime Cost Intelligence" in the Analysis nav group, reachable via `App.tsx`'s `case 'overtime'`. **Confirmed via live Playwright browser test** (not just TypeScript compiling): uploaded the real in-repo `test_employee_data.csv` fixture (200 rows, real `OverTime` Yes/No + `MonthlyIncome` columns), got real KPIs rendered — 33% overtime prevalence, SAR 112K/month, SAR 1.3M/year, 5-row department table — zero console errors. Screenshot on file.

**Methodology, cited:** Saudi Labour Law Art. 107 (overtime = wage + 50% minimum premium) and Art. 98 (48 hrs/week → 208 hrs/month basis), both real, specific, citable provisions. **One uncited engineering assumption, explicitly labeled as such (not fabricated as sourced):** when only a yes/no overtime flag exists (no hours column), 15 hours/month is assumed per flagged employee — the module's own docstring and every API response state plainly "this is an engineering assumption for illustrative purposes, NOT a sourced labour-market statistic," per the "do not fabricate precision" instruction.

---

## 5. Phase 2 — Payroll Movements Tracker

**Files created:**
- `backend/core/payroll_movement_tracker.py` (new, ~370 lines) — `analyze_payroll_movements(df, department_summary, employee_risk_scores=None)`, operating in one of 3 disclosed modes: `longitudinal` (real multi-period history), `cross_sectional_snapshot` (a recognized single-point indicator like `PercentSalaryHike`), or `unavailable`.
- `tests/test_payroll_movement_tracker.py` (new, 15 tests, **all passing**, covering all 3 modes with real assertions, including exact-value manual recomputation checks).
- `executive-ui/src/pages/PayrollMovementsTracker.tsx` (new page).

**Files modified:** same 4 files as Phase 1 (routes file, `types/index.ts`, `Sidebar.tsx`, `App.tsx`).

**Live route:** `POST /api/local/payroll-movements` — confirmed mounted.

**Live frontend page:** "Payroll Movements" nav item. **Confirmed via live Playwright test**: uploaded `test_employee_data.csv` (which genuinely has neither a period column nor a `PercentSalaryHike`-style column) and the page correctly rendered the honest "Not available for this dataset" state with a full explanation of what would activate the feature — verified this is the *correct* behavior, not a bug, since that fixture really is snapshot-only. Screenshot on file.

**No fabrication:** confirmed by `test_unavailable_result_has_no_fabricated_numbers` — when data doesn't support the analysis, `org_avg_hike_pct`/`n_periods_detected` are `None`, never a placeholder number.

---

## 6. Phase 3 — Exit Interview / Free-Text Intelligence

**Files created:**
- `backend/core/exit_interview_intelligence_engine.py` (new, ~330 lines) — `analyze_exit_interview_text(responses: list[str])`. Offline TF-IDF (scikit-learn `TfidfVectorizer`, guarded import with a deterministic word-frequency fallback) for salient-term extraction, plus a deterministic keyword classifier mapping responses to the **same** 10-construct subset of `employee_risk_scoring.py`'s existing `_CONSTRUCT_MAP` (JD-R/COR/Equity/Mobley/FFM theory anchors), labeled with the **same** `DIRECT`/`STRONG_PROXY`/`WEAK_PROXY` evidence taxonomy imported directly from `theory_aware_column_mapper.py` (not reinvented).
- `tests/test_exit_interview_intelligence_engine.py` (new, 18 tests, **all passing**), including dedicated privacy tests: `test_raw_response_text_never_appears_in_serialized_output`, `test_email_and_phone_are_scrubbed_and_never_surface_as_terms`, `test_one_off_identifying_detail_does_not_reach_min_document_frequency`.
- `executive-ui/src/pages/ExitInterviewIntelligence.tsx` (new page).

**Files modified:** same 4 nav-wiring files, plus `backend/api/local_analysis_routes.py` (+import, +`_parse_free_text_responses()` helper, +endpoint, +`import re` added to the file's top-level imports since it wasn't previously imported there).

**Live route:** `POST /api/local/exit-interview-intelligence` — confirmed mounted. Accepts a **separate** upload (`.txt` one-response-per-line, or `.csv`/`.xlsx` with a free-text column) — never runs on the structured HR dataset itself, per the brief's "clearly optional" requirement.

**Live frontend page:** "Exit Interview Intelligence" nav item. **Confirmed via live Playwright test**: page loads cleanly with the upload widget, PII/governance disclaimers, and "do not upload employee names" warning visible. (Upload-and-analyze was verified at the unit-test level with 18 real assertions rather than in the browser, since it requires a `.txt` fixture the repo doesn't already have — the backend logic itself was exercised directly and thoroughly.)

**Privacy guarantees (verified, not just claimed):** every response is regex-scrubbed for emails/phones/national-ID patterns before processing; a term must appear in **≥3 distinct responses** (`MIN_DOCUMENT_FREQUENCY`) to surface at all — proven in `test_one_off_identifying_detail_does_not_reach_min_document_frequency`, which plants a fictional name in one response among 7 and confirms it never appears in the output; aggregation requires **≥5 total responses** before any output is produced at all.

---

## 7. Phase 4 — Sector-Based Benchmarking (Real Sources, Honest Fallback)

**Research performed:** live web search + fetch (not memory) for a freely-available, precisely-citable Saudi/GCC benchmark broken down by the existing industry-vertical taxonomy (banking/oil_gas/telecom/government/healthcare/construction/retail). **Result: no such free, precisely-citable source was found** — the detailed GCC salary surveys that exist (Hays, Mercer, Korn Ferry, GulfTalent) are commercial/gated, and per this task's explicit "do not fabricate" instruction, their headline numbers cannot be reproduced here without a citable source.

**What WAS found and is real:** GASTAT (Saudi Arabia's General Authority for Statistics) — official government statistics, freely published:
- "Labor Market Bulletin, Q2 2018" (published 2018-11-21): average monthly wage by **employment-sector type** — Public SAR 11,198, Private SAR 7,339, Non-profit SAR 4,750, International/Regional SAR 16,257. Source: https://www.stats.gov.sa/en/w/gastat-saudi-workers-monthly-average-wage-in-four-sectors-10.238-sar
- More recent overall figure (Q3 2024): SAR 10,119/month for Saudi nationals vs. SAR 4,202 for non-Saudi workers (per GASTAT, cited via Argaam).

This is a **different dimension** (employment-sector type: public/private/non-profit/international) than the existing industry-vertical table (banking/oil_gas/etc.) — both are now implemented, honestly labeled, and the more reliable one is preferred whenever it can be determined.

**What changed in `backend/core/financial_intelligence_engine.py`** (all additive — verified zero breaking changes to the 6 existing call sites, all 40 Phase 0 tests still pass):

| Addition | Detail |
|---|---|
| `SECTOR_BENCHMARK_CONFIDENCE = "uncalibrated_generic_estimate"` + `SECTOR_BENCHMARK_DISCLAIMER` | Honestly labels the **existing** industry-vertical table as uncalibrated, per this task's explicit fallback instruction — not deleted (still a reasonable relative-ordering heuristic), but never again presented as sourced. |
| `EMPLOYMENT_SECTOR_SALARY_SAR` + `EMPLOYMENT_SECTOR_SOURCE` + `EMPLOYMENT_SECTOR_BENCHMARK_CONFIDENCE = "gastat_official_2018"` | The real, cited data above. |
| `infer_employment_sector_from_metadata(department_summary, sector_column_values)` | Returns `"public"`/`"private"`/`"non_profit"`/`"international_regional"`, or **`None`** — never a silent guess — when no real signal exists in an explicit sector/employer-type column or department names. |
| `estimate_monthly_salary(..., *, employment_sector=None)` | New keyword-only parameter. Precedence: real observed salary column > GASTAT-cited `employment_sector` > uncalibrated industry-vertical `sector`. |
| `salary_benchmark_confidence_for(...)` + a new `salary_benchmark_confidence` field on `DepartureCostEstimate`/`WorkforceExposureEstimate` (default-valued, backward compatible) | Every dollar figure this module produces now carries an honest provenance label — `"observed"`, `"gastat_official_2018"`, or `"uncalibrated_generic_estimate"` — surfaced through to `departure_cost_to_dict()`/`workforce_exposure_to_dict()`. |

**Integration:** `backend/core/executive_roi_engine.py` (the main sector/seniority-aware ROI computation, and the highest-leverage single integration point since 15 downstream report call sites all flow through it indirectly via `WorkforceExposureEstimate`) now calls `infer_employment_sector_from_metadata()` first and only falls back to the uncalibrated table when no real signal exists. **Verified live:** a `department_summary` containing "Ministry of Education" now correctly triggers `salary_benchmark_confidence="gastat_official_2018"` and the real SAR 11,198 base salary; a generic "Sales" department correctly falls back to `"uncalibrated_generic_estimate"` — confirmed by direct execution, not just reading the code.

**Tests:** `tests/test_sector_benchmarking_phase4.py` (new, 17 tests, **all passing**) — covers both benchmark tiers, precedence ordering (observed > GASTAT > uncalibrated), the "no silent guessing" requirement for inference, and that an invalid/unrecognized `employment_sector` string falls back to the honest label rather than silently accepting garbage input.

**Follow-up completed (update, same session):** the 15 report-exporter call sites (PDF/PPTX/slide, from Phase 0) initially still called `estimate_workforce_financial_exposure(at_risk)` without an `employment_sector` argument, because department context wasn't yet threaded into their scope. This has now been closed:

- Added a per-file `infer_employment_sector_from_metadata(...)` call at every one of the 15 sites — reusing each function's already-extracted `department_summary`/`dept_sum` local variable (`executive_pdf_exporter.py`, `executive_slide_exporter.py`) or a new small `_employment_sector(data)` module-level helper mirroring the file's existing `_at_risk(data)` pattern (`executive_pptx_exporter.py`, which has 11 call sites, not the 10 originally counted in Phase 0 — corrected here).
- Org-wide call sites pass the full `department_summary`; per-department call sites (inside department-ranking loops) pass just that one department's dict, so a mixed-sector organization gets a per-department inference rather than one blended guess.
- **Verified with real output-diffing, not just import checks:** `generate_slide_deck()`, `generate_pptx()`, and `ExecutivePDFExporter.generate()` were each called twice with identical inputs except department name ("Ministry of Labour" vs. "Sales") — confirmed the generated HTML/PPTX bytes genuinely differ, proving the inference actually reaches the rendered output, not just that the import resolves.
- **Tests:** `tests/test_sector_benchmarking_phase4.py` grew from 17 to **23 tests** (6 new: 3 output-diffing tests, one per exporter, plus 3 import-regression guards). All passing.
- Full-suite regression re-run after this change: same 39 pre-existing failures, **1217 passed** (was 1211) — zero regressions.

---

## Summary Table

| Phase | New files | Modified files | New tests | Live route(s) | Live frontend page | Status |
|---|---|---|---|---|---|---|
| 0 | 1 (`financial_intelligence_engine.py`) | 6 | 40 | n/a (internal) | n/a | ✅ Complete, verified |
| 0.5 | 0 | 3 (`tenant_manager.py`, `historical_intelligence_engine.py`, `local_analysis_routes.py` bonus fix) | 0 (existing tests updated) | n/a | n/a | ✅ Complete, verified |
| 1 | 3 | 4 | 15 | `POST /api/local/overtime-cost-intelligence` | Overtime Cost Intelligence | ✅ Complete, browser-verified |
| 2 | 3 | 4 | 15 | `POST /api/local/payroll-movements` | Payroll Movements | ✅ Complete, browser-verified |
| 3 | 3 | 5 | 18 | `POST /api/local/exit-interview-intelligence` | Exit Interview Intelligence | ✅ Complete, browser-verified |
| 4 | 1 (this report) | 5 (`financial_intelligence_engine.py`, `executive_roi_engine.py`, `executive_pdf_exporter.py`, `executive_pptx_exporter.py`, `executive_slide_exporter.py`) | 23 | n/a (integrated into ROI pipeline + all 3 exporters) | n/a (backend enhancement) | ✅ Complete, verified, exporter follow-up closed |
| **Total** | **11 new files** | **~14 modified files** (some overlap across phases) | **111 new tests, all passing** | **3 new live endpoints** | **3 new live pages** | |

**Operational note:** during live browser verification, a backend dev-server process on port 8000 could not be cleanly stopped from this shell after testing completed (it may be in a different process namespace than what `taskkill` from this session can signal) — the frontend dev server was confirmed stopped. If port 8000 is still bound when you next try to start the backend yourself, check for and stop that process manually.
